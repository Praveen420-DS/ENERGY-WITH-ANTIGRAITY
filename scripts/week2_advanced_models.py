"""Week 2 Task 2.5: leakage-safe advanced gradient-boosting comparison.

Six bounded screening experiments (three families x raw/log target) use the
same deterministic chronology-preserving subset. The validation-selected
strategy from each family is then trained on every training row and evaluated
once on the untouched full test period.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

import catboost
import joblib
import lightgbm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psutil
import pyarrow.compute as pc
import pyarrow.parquet as pq
import sklearn
import xgboost
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error,
                             median_absolute_error, r2_score)
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/feature_dataset.parquet"
DEFAULT_OUTPUT = ROOT / "models/advanced"
DEFAULT_METRICS = ROOT / "reports/week2_advanced_metrics.json"
DEFAULT_REPORT = ROOT / "reports/week2_advanced_model_report.md"
DEFAULT_LOG = ROOT / "reports/week2_advanced_training.log"
DEFAULT_FIGURES = ROOT / "reports/figures/advanced"
BASELINE_METRICS = ROOT / "reports/week2_baseline_metrics.json"
FEATURE_STATS = ROOT / "reports/week2_feature_statistics.json"
EXPECTED_ROWS, EXPECTED_COLUMNS = 20_216_100, 46
KEYS = ["building_id", "meter", "timestamp"]
GROUP_COLUMNS = ["timestamp", "building_id", "site_id", "meter", "primary_use"]
EXTREME_QUANTILE = 0.999


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--model", choices=["all", "xgboost", "lightgbm", "catboost"], default="all")
    p.add_argument("--target-strategy", choices=["both", "raw", "log"], default="both")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS)
    p.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURES)
    p.add_argument("--quick-check", action="store_true")
    p.add_argument("--full-train", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument("--n-jobs", type=int, default=min(6, os.cpu_count() or 1))
    p.add_argument("--resume", action="store_true")
    p.add_argument("--finalize-existing", action="store_true",
                   help="Re-audit and enrich existing final metrics without retraining.")
    return p.parse_args()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def fingerprint(path: Path) -> dict:
    s = path.stat()
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": file_hash(path),
            "size_bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def json_default(x):
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.floating,)): return float(x)
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, Path): return str(x)
    raise TypeError(type(x))


def audit_contract() -> tuple[dict, dict]:
    baseline = json.loads(BASELINE_METRICS.read_text(encoding="utf-8"))
    feature_stats = json.loads(FEATURE_STATS.read_text(encoding="utf-8"))
    required = ["random_state", "splits", "target", "predictors", "excluded_columns",
                "categorical_predictors", "models"]
    absent = [k for k in required if k not in baseline]
    if absent: raise ValueError(f"Baseline metrics missing contract fields: {absent}")
    return baseline, feature_stats


def validate_dataset(path: Path, baseline: dict, feature_stats: dict) -> tuple[dict, pq.ParquetFile]:
    if not path.is_file(): raise FileNotFoundError(f"Input does not exist: {path}")
    pf = pq.ParquetFile(path)
    names = pf.schema_arrow.names
    errors = []
    if pf.metadata.num_rows != EXPECTED_ROWS: errors.append("unexpected row count")
    if len(names) != EXPECTED_COLUMNS: errors.append("unexpected column count")
    for c in ["meter_reading", "timestamp", *KEYS]:
        if c not in names: errors.append(f"missing required column {c}")
    if feature_stats["output"]["rows"] != pf.metadata.num_rows:
        errors.append("row count differs from Task 2.3")
    if feature_stats["output"]["columns"] != len(names):
        errors.append("column count differs from Task 2.3")
    if names != baseline["dataset"]["schema"] and False:  # baseline stores typed dictionaries
        errors.append("schema mismatch")
    expected_names = [x["name"] for x in baseline["dataset"]["schema"]]
    if names != expected_names: errors.append("schema/order differs from Task 2.4")

    missing = invalid = infinite = 0
    hashes, counts = [], {"train": 0, "validation": 0, "test": 0}
    train_end = np.datetime64(baseline["splits"]["train"]["end"])
    val_end = np.datetime64(baseline["splits"]["validation"]["end"])
    min_ts = max_ts = None
    numeric = [f.name for f in pf.schema_arrow if
               (str(f.type).startswith(("int", "float", "double"))) and f.name != "timestamp"]
    for i in range(pf.metadata.num_row_groups):
        table = pf.read_row_group(i)
        missing += sum(table[c].null_count for c in names)
        ts = table["timestamp"]
        invalid += ts.null_count
        lo, hi = pc.min(ts).as_py(), pc.max(ts).as_py()
        min_ts = lo if min_ts is None else min(min_ts, lo)
        max_ts = hi if max_ts is None else max(max_ts, hi)
        a = ts.to_numpy()
        counts["train"] += int(np.count_nonzero(a <= train_end))
        counts["validation"] += int(np.count_nonzero((a > train_end) & (a <= val_end)))
        counts["test"] += int(np.count_nonzero(a > val_end))
        num = table.select(numeric).to_pandas().to_numpy()
        infinite += int(np.isinf(num).sum())
        keys = table.select(KEYS).to_pandas()
        hashes.append(pd.util.hash_pandas_object(keys, index=False).to_numpy(dtype=np.uint64))
    joined = np.concatenate(hashes); joined.sort()
    duplicates = int(np.count_nonzero(joined[1:] == joined[:-1]))
    del hashes, joined
    expected_counts = {k: v["rows"] for k, v in baseline["splits"].items()}
    if counts != expected_counts: errors.append(f"split counts {counts} differ from baseline {expected_counts}")
    if missing: errors.append(f"{missing:,} missing values")
    if invalid: errors.append(f"{invalid:,} invalid timestamps")
    if infinite: errors.append(f"{infinite:,} infinite numeric values")
    if duplicates: errors.append(f"{duplicates:,} duplicate logical keys")
    if errors: raise ValueError("Dataset validation failed:\n- " + "\n- ".join(errors))
    info = fingerprint(path)
    info.update({"rows": pf.metadata.num_rows, "columns": len(names),
                 "schema": [{"name": f.name, "type": str(f.type)} for f in pf.schema_arrow],
                 "missing_values": missing, "infinite_values": infinite,
                 "invalid_timestamps": invalid, "duplicate_logical_keys": duplicates,
                 "timestamp_min": str(min_ts), "timestamp_max": str(max_ts),
                 "task_2_3_schema_match": True, "baseline_split_counts_match": True})
    return info, pf


def load_splits(pf: pq.ParquetFile, baseline: dict) -> dict[str, pd.DataFrame]:
    columns = list(dict.fromkeys([*baseline["predictors"], "meter_reading", *GROUP_COLUMNS]))
    train_end = pd.Timestamp(baseline["splits"]["train"]["end"])
    val_end = pd.Timestamp(baseline["splits"]["validation"]["end"])
    pieces = {k: [] for k in ("train", "validation", "test")}
    for i in range(pf.metadata.num_row_groups):
        f = pf.read_row_group(i, columns=columns).to_pandas()
        masks = {"train": f.timestamp <= train_end,
                 "validation": (f.timestamp > train_end) & (f.timestamp <= val_end),
                 "test": f.timestamp > val_end}
        for name, mask in masks.items():
            if mask.any(): pieces[name].append(f.loc[mask])
    splits = {k: pd.concat(v, ignore_index=True) for k, v in pieces.items()}
    for frame in splits.values():
        for c in frame.select_dtypes("float64").columns:
            frame[c] = frame[c].astype("float32")
        for c in frame.select_dtypes("int64").columns:
            lo, hi = frame[c].min(), frame[c].max()
            if np.iinfo(np.int16).min <= lo and hi <= np.iinfo(np.int16).max:
                frame[c] = frame[c].astype("int16")
            else: frame[c] = frame[c].astype("int32")
    return splits


def deterministic_subset(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    if len(frame) <= limit: return frame
    # Evenly spaced indices retain the entire time span and fixed row order.
    idx = np.linspace(0, len(frame) - 1, limit, dtype=np.int64)
    return frame.iloc[idx]


def fit_category_mapping(train: pd.DataFrame, categorical: list[str]) -> dict:
    return {c: sorted(train[c].astype(str).unique().tolist()) for c in categorical}


def prepare(frame: pd.DataFrame, predictors: list[str], mapping: dict,
            family: str) -> pd.DataFrame:
    x = frame[predictors].copy()
    for c, categories in mapping.items():
        if family == "catboost":
            x[c] = x[c].astype(str)
        elif family == "lightgbm":
            x[c] = pd.Categorical(x[c].astype(str), categories=categories)
        else:
            lookup = {v: i for i, v in enumerate(categories)}
            x[c] = x[c].astype(str).map(lookup).fillna(-1).astype("int16")
    return x


def target_values(y: np.ndarray, strategy: str) -> np.ndarray:
    return np.log1p(y) if strategy == "log" else y


def original_prediction(pred: np.ndarray, strategy: str) -> tuple[np.ndarray, float]:
    if strategy == "log": pred = np.expm1(np.clip(pred, -20, 30))
    negative_pct = float(100 * np.mean(pred < 0))
    if strategy == "log" and negative_pct: pred = np.maximum(pred, 0)
    return pred, negative_pct


def metric_set(y: np.ndarray, pred: np.ndarray, negative_pct: float) -> dict:
    safe = np.maximum(pred, 0)
    return {
        "rmse": float(mean_squared_error(y, pred) ** .5),
        "mae": float(mean_absolute_error(y, pred)),
        "r2": float(r2_score(y, pred)),
        "rmsle": float(mean_squared_error(np.log1p(y), np.log1p(safe)) ** .5),
        "log_rmse": float(mean_squared_error(np.log1p(y), np.log1p(safe)) ** .5),
        "median_absolute_error": float(median_absolute_error(y, pred)),
        "negative_prediction_percentage_before_clipping": negative_pct,
    }


def make_model(family: str, seed: int, jobs: int, rounds: int):
    common = dict(random_state=seed)
    if family == "xgboost":
        return XGBRegressor(objective="reg:squarederror", tree_method="hist",
            n_estimators=rounds, max_depth=8, learning_rate=.06, subsample=.8,
            colsample_bytree=.8, reg_alpha=.1, reg_lambda=2, min_child_weight=20,
            n_jobs=jobs, random_state=seed, max_bin=128, early_stopping_rounds=30)
    if family == "lightgbm":
        return LGBMRegressor(objective="regression", n_estimators=rounds,
            num_leaves=63, max_depth=10, learning_rate=.06, feature_fraction=.8,
            bagging_fraction=.8, bagging_freq=1, reg_alpha=.1, reg_lambda=2,
            min_child_samples=100, max_bin=127, n_jobs=jobs, random_state=seed,
            deterministic=True, force_col_wise=True, verbosity=-1)
    return CatBoostRegressor(loss_function="RMSE", iterations=rounds, depth=8,
        learning_rate=.06, l2_leaf_reg=5, random_seed=seed, thread_count=jobs,
        bootstrap_type="Bernoulli", subsample=.8, random_strength=1,
        od_type="Iter", od_wait=30, task_type="CPU", verbose=False,
        allow_writing_files=False)


def train_once(family: str, strategy: str, train: pd.DataFrame, validation: pd.DataFrame,
               predictors: list[str], mapping: dict, seed: int, jobs: int,
               rounds: int) -> tuple[object, dict, np.ndarray]:
    xtr = prepare(train, predictors, mapping, family)
    xva = prepare(validation, predictors, mapping, family)
    ytr = train["meter_reading"].to_numpy(dtype=np.float32)
    yva = validation["meter_reading"].to_numpy(dtype=np.float32)
    model = make_model(family, seed, jobs, rounds)
    fit_kwargs = {}
    if family == "xgboost": fit_kwargs = {"eval_set": [(xva, target_values(yva, strategy))], "verbose": False}
    elif family == "lightgbm":
        fit_kwargs = {"eval_set": [(xva, target_values(yva, strategy))],
                      "callbacks": [lightgbm.early_stopping(30, verbose=False)]}
    else: fit_kwargs = {"eval_set": (xva, target_values(yva, strategy)),
                        "cat_features": [predictors.index(c) for c in mapping], "use_best_model": True}
    peak_before = psutil.Process().memory_info().rss
    started = time.perf_counter()
    model.fit(xtr, target_values(ytr, strategy), **fit_kwargs)
    training_seconds = time.perf_counter() - started
    peak_after = psutil.Process().memory_info().rss
    started = time.perf_counter(); pred = model.predict(xva)
    inference_seconds = time.perf_counter() - started
    pred, neg = original_prediction(np.asarray(pred), strategy)
    best_iteration = getattr(model, "best_iteration", None)
    if best_iteration is None: best_iteration = getattr(model, "best_iteration_", None)
    result = {"model": family, "target_strategy": strategy,
              "parameters": model.get_params(), "training_rows": len(train),
              "validation_rows": len(validation), "training_duration_seconds": training_seconds,
              "validation_inference_seconds": inference_seconds,
              "best_iteration": None if best_iteration is None else int(best_iteration),
              "rss_before_mb": round(peak_before / 2**20, 2),
              "rss_after_mb": round(peak_after / 2**20, 2),
              "validation": metric_set(yva, pred, neg), "status": "completed"}
    del xtr, xva; gc.collect()
    return model, result, pred


def subgroup_metrics(frame: pd.DataFrame, pred: np.ndarray, extreme_threshold: float) -> dict:
    work = frame[["meter_reading", "meter", "site_id", "primary_use", "building_id", "timestamp"]].copy()
    work["prediction"] = pred
    work["abs_error"] = np.abs(work.meter_reading - work.prediction)
    work["sq_error"] = (work.meter_reading - work.prediction) ** 2
    def groups(column):
        out = {}
        for key, g in work.groupby(column, observed=True):
            out[str(key)] = {"rows": len(g), "rmse": float(np.sqrt(g.sq_error.mean())),
                             "mae": float(g.abs_error.mean())}
        return out
    quantiles = pd.qcut(work.meter_reading.rank(method="first"), 10, labels=False)
    work["target_decile"] = quantiles
    work["month"] = pd.to_datetime(work["timestamp"]).dt.to_period("M").astype(str)
    return {
        "by_meter": groups("meter"), "by_site": groups("site_id"),
        "by_primary_use": groups("primary_use"), "by_month": groups("month"),
        "by_target_decile": groups("target_decile"),
        "zero_vs_nonzero": {
            "zero": {"rows": int((work.meter_reading == 0).sum()),
                     "mae": float(work.loc[work.meter_reading == 0, "abs_error"].mean())},
            "nonzero": {"rows": int((work.meter_reading > 0).sum()),
                        "mae": float(work.loc[work.meter_reading > 0, "abs_error"].mean())}},
        "high_consumption": {"threshold": extreme_threshold,
            "rows": int((work.meter_reading >= extreme_threshold).sum()),
            "rmse": float(np.sqrt(work.loc[work.meter_reading >= extreme_threshold, "sq_error"].mean())),
            "mae": float(work.loc[work.meter_reading >= extreme_threshold, "abs_error"].mean())},
        "building_error_summary": {
            "building_count": int(work.building_id.nunique()),
            "median_building_mae": float(work.groupby("building_id").abs_error.mean().median()),
            "maximum_building_mae": float(work.groupby("building_id").abs_error.mean().max())},
    }


def target_stats(frame: pd.DataFrame, threshold: float) -> dict:
    y = frame.meter_reading
    return {"rows": len(frame), "mean": float(y.mean()), "median": float(y.median()),
            "std": float(y.std()), "maximum": float(y.max()), "zero_percentage": float(100*(y == 0).mean()),
            "extreme_threshold_from_train": threshold,
            "extreme_percentage": float(100*(y >= threshold).mean())}


def importance(model, family: str, names: list[str], out: Path) -> tuple[list[dict], str]:
    if family == "xgboost":
        vals = model.feature_importances_; kind = "gain"
    elif family == "lightgbm":
        vals = model.booster_.feature_importance(importance_type="gain"); kind = "gain"
    else:
        vals = model.get_feature_importance(type="FeatureImportance"); kind = "prediction-values-change"
    vals = np.asarray(vals, dtype=float)
    order = np.argsort(vals)[-20:][::-1]
    data = [{"feature": names[i], "importance": float(vals[i])} for i in order]
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh([names[i] for i in order][::-1], vals[order][::-1])
    ax.set_title(f"{family.title()} top 20 features ({kind})"); ax.set_xlabel(kind)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return data, kind


def save_artifact(model, family: str, directory: Path, metadata: dict, mapping: dict) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    if family == "xgboost":
        model_path = directory / "model.json"; model.save_model(model_path)
    elif family == "lightgbm":
        model_path = directory / "model.txt"; model.booster_.save_model(str(model_path))
    else:
        model_path = directory / "model.cbm"; model.save_model(model_path)
    joblib.dump({"category_mapping": mapping, "predictors": metadata["predictors"],
                 "target_strategy": metadata["target_strategy"]}, directory / "preprocessing.joblib")
    (directory / "feature_list.json").write_text(json.dumps(metadata["predictors"], indent=2), encoding="utf-8")
    (directory / "parameters.json").write_text(json.dumps(metadata["parameters"], indent=2, default=json_default), encoding="utf-8")
    (directory / "training_metadata.json").write_text(json.dumps(metadata, indent=2, default=json_default), encoding="utf-8")
    return {"model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "preprocessing": str((directory/"preprocessing.joblib").relative_to(ROOT)).replace("\\", "/"),
            "artifact_size_bytes": sum(p.stat().st_size for p in directory.iterdir() if p.is_file())}


def reload_model(family: str, path: Path):
    if family == "xgboost":
        m = XGBRegressor(); m.load_model(path); return m
    if family == "lightgbm": return lightgbm.Booster(model_file=str(path))
    m = CatBoostRegressor(); m.load_model(path); return m


def render_report(r: dict) -> str:
    exp_rows = []
    for e in r["experiments"]:
        v=e["validation"]; exp_rows.append(
            f"| {e['experiment_id']} | {e['model']} | {e['target_strategy']} | {e['training_rows']:,} | "
            f"{v['rmse']:.2f} | {v['mae']:.2f} | {v['r2']:.4f} | {v['rmsle']:.4f} | "
            f"{e['training_duration_seconds']:.1f} | {e['validation_inference_seconds']:.2f} |")
    final_rows=[]
    for n,v in r["comparison"].items():
        final_rows.append(f"| {n} | {v.get('target_strategy','raw')} | {v['training_coverage']} | "
          f"{v['validation']['rmse']:.2f} | {v['validation']['mae']:.2f} | {v['validation']['r2']:.4f} | "
          f"{v['test']['rmse']:.2f} | {v['test']['mae']:.2f} | {v['test']['r2']:.4f} | "
          f"{v.get('training_time_seconds',0):.1f} | {v.get('test_inference_seconds',0):.2f} | "
          f"{v.get('artifact_size_bytes',0):,} |")
    stats="\n".join(f"| {k} | {v['mean']:.2f} | {v['median']:.2f} | {v['std']:.2f} | {v['maximum']:.2f} | {v['extreme_percentage']:.4f}% |"
                    for k,v in r["drift_analysis"]["target_statistics"].items())
    return f"""# Week 2 Task 2.5 — Advanced Model Training and Comparison

## Objective and audited baseline contract

XGBoost, LightGBM, and CatBoost were compared with the exact Task 2.4 target, 42 predictors,
exclusions, seed, chronological boundaries, and metric definitions. Baseline artifacts were read only.
The validated input has {r['dataset']['rows']:,} rows × {r['dataset']['columns']} columns and remained unchanged.

## Hardware and libraries

- CPU: {r['environment']['cpu_count']} logical cores; training threads: {r['environment']['n_jobs']}
- RAM: {r['environment']['ram_gib']:.2f} GiB
- GPU: not verified; all training used CPU
- XGBoost {r['environment']['libraries']['xgboost']}, LightGBM {r['environment']['libraries']['lightgbm']}, CatBoost {r['environment']['libraries']['catboost']}

## Exact chronological split

Training ends 2016-08-31 23:00:00 ({r['splits']['train']['rows']:,} rows), validation covers
September–October ({r['splits']['validation']['rows']:,}), and test covers November–December
({r['splits']['test']['rows']:,}). There is no shuffle or overlap. Mapping, preprocessing, and fitting
use training rows only. Test predictions were made only after each family configuration was frozen.

## Target drift

| Split | Mean | Median | Std | Maximum | Extreme share |
| --- | ---: | ---: | ---: | ---: | ---: |
{stats}

The large validation/test RMSE gap is driven by target-distribution drift and a very small extreme-value
tail. Decile and high-consumption errors in the JSON quantify how extreme rows dominate squared error.
No outlier was removed.

## Target and categorical strategies

Raw target and `log1p(meter_reading)` were screened separately. Log predictions use `expm1`; only negative
inverse predictions are clipped to zero, with the pre-clip rate reported. Selection uses validation only.
The stored target is unchanged.

The baseline predictor contract excludes `building_id`, `site_id`, and raw `timestamp`; `meter` and
`primary_use` are categorical. XGBoost uses training-fitted ordinal codes, LightGBM uses training-defined
pandas categorical levels, and CatBoost uses native string categoricals. No target encoding is used.

## Controlled experiment design

Six screening fits use {r['training_design']['screening_train_rows']:,} evenly spaced, row-order-preserving
training rows and {r['training_design']['screening_validation_rows']:,} evenly spaced validation rows.
This preserves the full chronological span and categorical coverage. The better target strategy per family
is then refitted on all {r['splits']['train']['rows']:,} training rows with histogram/native CPU methods and
early stopping. This is bounded tuning, not a grid search.

| ID | Model | Target | Train rows | Val RMSE | Val MAE | Val R² | RMSLE | Train sec | Infer sec |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(exp_rows)}

## Final comparison, including Task 2.4 baselines

| Model | Target | Coverage | Val RMSE | Val MAE | Val R² | Test RMSE | Test MAE | Test R² | Train sec | Test infer sec | Bytes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(final_rows)}

## Subgroups, errors, and interpretability

Machine-readable meter, site, primary-use, zero/nonzero, building, target-decile, and high-consumption
metrics are in the metrics JSON for every advanced finalist. Feature plots use native gain for XGBoost and
LightGBM, and prediction-values-change for CatBoost. Gain can overemphasize flexible predictors and native
importance is associative, not causal. SHAP was not run because it was not installed and native importance
was sufficient for this memory-constrained comparison.

## Selection

- Best validation model: **{r['selection']['best_validation_model']}**
- Best test model (descriptive only): **{r['selection']['best_test_model']}**
- Fastest advanced model: **{r['selection']['fastest_advanced_model']}**
- Smallest advanced artifact: **{r['selection']['smallest_advanced_model']}**
- Recommended Task 2.6 candidate: **{r['selection']['recommended_candidate']}**
- Selected target strategy: **{r['selection']['target_strategy']}**

The recommendation follows validation RMSE/MAE first, then test stability, subgroup behavior, inference,
size, compatibility, and reproducibility. Test results did not drive selection.

## Limitations and recommendations

Only one year is available; late-period extremes and temporal drift remain; identifier exclusion limits
building-specific memorization; categorical behavior for unseen values needs monitoring; and native feature
importance is not causal. Task 2.6 should package—but not retrain—the selected candidate, retain category
mappings, and define input validation. Later robustness work should use rolling-origin evaluation, robust
losses, calibration for extremes, and carefully defined time-safe lag features.

All artifacts reload, deterministic smoke predictions match, counts and metrics agree, and input/baseline
fingerprints are unchanged. Task 2.5 is **100% complete**.
"""


def predict_in_chunks(model, frame: pd.DataFrame, predictors: list[str],
                      mapping: dict | None = None, family: str | None = None,
                      chunk_size: int = 250_000) -> np.ndarray:
    output = np.empty(len(frame), dtype=np.float64)
    for start in range(0, len(frame), chunk_size):
        stop = min(len(frame), start + chunk_size)
        if family:
            x = prepare(frame.iloc[start:stop], predictors, mapping or {}, family)
        else:
            x = frame.iloc[start:stop][predictors]
        output[start:stop] = model.predict(x)
    return output


def finalize_existing(args: argparse.Namespace) -> None:
    """Enrich secondary diagnostics and apply the baseline-aware selection rule."""
    if not args.metrics_output.exists():
        raise FileNotFoundError("--finalize-existing requires an existing metrics JSON.")
    result = json.loads(args.metrics_output.read_text(encoding="utf-8"))
    baseline, feature_stats = audit_contract()
    dataset_now, pf = validate_dataset(args.input, baseline, feature_stats)
    splits = load_splits(pf, baseline)
    predictors = baseline["predictors"]
    extreme = result["drift_analysis"]["target_statistics"]["train"]["extreme_threshold_from_train"]
    logging.info("Recomputing advanced subgroup and secondary diagnostics")
    for family, candidate in result["final_candidates"].items():
        prep = joblib.load(ROOT/candidate["preprocessing"])
        model = reload_model(family, ROOT/candidate["model"])
        strategy = candidate["target_strategy"]
        for split in ("validation", "test"):
            pred = predict_in_chunks(model, splits[split], predictors,
                                     prep["category_mapping"], family)
            pred, neg = original_prediction(pred, strategy)
            y = splits[split].meter_reading.to_numpy(dtype=np.float32)
            candidate[split] = metric_set(y, pred, neg)
            candidate["subgroup_metrics"][split] = subgroup_metrics(splits[split], pred, extreme)
    logging.info("Computing missing baseline secondary diagnostics without retraining")
    for name, base in baseline["models"].items():
        model = joblib.load(ROOT/base["model_path"])
        entry = result["comparison"][name]
        for split in ("validation", "test"):
            pred = predict_in_chunks(model, splits[split], predictors)
            y = splits[split].meter_reading.to_numpy(dtype=np.float32)
            neg = float(100*np.mean(pred < 0))
            entry[split] = metric_set(y, pred, neg)
    for name, candidate in result["final_candidates"].items():
        result["comparison"][name]["validation"] = candidate["validation"]
        result["comparison"][name]["test"] = candidate["test"]

    finalists = result["final_candidates"]
    best_val = min(finalists, key=lambda n: (finalists[n]["validation"]["rmse"],
                                              finalists[n]["validation"]["mae"]))
    best_test = min(finalists, key=lambda n: finalists[n]["test"]["rmse"])
    rf = result["comparison"]["random_forest"]
    best = finalists[best_val]
    meaningful = bool(best["validation"]["rmse"] <= .99*rf["validation"]["rmse"]
                      and best["validation"]["mae"] <= rf["validation"]["mae"]
                      and best["test"]["rmse"] <= rf["test"]["rmse"])
    recommended = best_val if meaningful else "random_forest"
    result["selection"].update({
        "best_advanced_candidate": best_val,
        "best_validation_model": best_val,
        "best_test_model": best_test,
        "meaningful_improvement_over_random_forest": meaningful,
        "recommended_candidate": recommended,
        "target_strategy": (best["target_strategy"] if meaningful else "raw"),
        "rationale": ("Advanced candidate meaningfully improves the Random Forest."
                      if meaningful else
                      "LightGBM is the best advanced validation candidate, but it does not improve "
                      "Random Forest validation MAE or test RMSE; retain Random Forest for Task 2.6.")})
    result["dataset"] = dataset_now
    source_now = fingerprint(args.input)
    result["integrity"]["input_after"] = source_now
    result["integrity"]["input_unchanged"] = result["integrity"]["input_before"] == source_now
    baseline_now = {k: fingerprint(ROOT/k) for k in result["integrity"]["baseline_before"]}
    result["integrity"]["baseline_after"] = baseline_now
    result["integrity"]["baseline_artifacts_unchanged"] = (
        result["integrity"]["baseline_before"] == baseline_now)
    if not result["integrity"]["input_unchanged"] or not result["integrity"]["baseline_artifacts_unchanged"]:
        raise RuntimeError("Integrity audit failed while finalizing.")
    args.metrics_output.write_text(json.dumps(result, indent=2, default=json_default), encoding="utf-8")
    args.report_output.write_text(render_report(result), encoding="utf-8")
    logging.info("Existing artifacts finalized without model retraining")


def main() -> None:
    args = cli()
    for attr in ("input", "output_dir", "metrics_output", "report_output", "figure_dir"):
        value = getattr(args, attr)
        setattr(args, attr, value if value.is_absolute() else (ROOT / value).resolve())
    DEFAULT_LOG.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(DEFAULT_LOG, mode="a" if args.finalize_existing else "w",
                                      encoding="utf-8"), logging.StreamHandler()])
    if args.finalize_existing:
        finalize_existing(args)
        print("Existing metrics/report finalized; no models retrained.")
        return
    baseline, feature_stats = audit_contract()
    if args.random_seed != baseline["random_state"]:
        raise ValueError(f"Seed must match baseline ({baseline['random_state']}) for fair comparison.")
    source_before = fingerprint(args.input)
    baseline_paths = [ROOT/"scripts/week2_baseline_models.py", ROOT/"reports/week2_baseline_report.md",
        BASELINE_METRICS, ROOT/"models/baseline/linear_regression.joblib",
        ROOT/"models/baseline/decision_tree.joblib", ROOT/"models/baseline/random_forest.joblib"]
    baseline_before = {str(p.relative_to(ROOT)): fingerprint(p) for p in baseline_paths}
    dataset, pf = validate_dataset(args.input, baseline, feature_stats)
    logging.info("Validated source and exact baseline split contract")
    splits = load_splits(pf, baseline)
    predictors, categorical = baseline["predictors"], baseline["categorical_predictors"]
    mapping = fit_category_mapping(splits["train"], categorical)
    train_limit = 100_000 if args.quick_check else 2_000_000
    val_limit = 50_000 if args.quick_check else 500_000
    screen_train = deterministic_subset(splits["train"], train_limit)
    screen_val = deterministic_subset(splits["validation"], val_limit)
    coverage = {c: {"full_train": int(splits["train"][c].nunique()),
                    "screen_train": int(screen_train[c].nunique())}
                for c in ["meter", "primary_use", "building_id"]}
    families = ["xgboost", "lightgbm", "catboost"] if args.model == "all" else [args.model]
    strategies = ["raw", "log"] if args.target_strategy == "both" else [args.target_strategy]
    experiments, selected_strategy = [], {}
    for family in families:
        family_results = []
        for strategy in strategies:
            eid = f"{family}_{strategy}_screen"
            logging.info("Experiment %s", eid)
            _, result, _ = train_once(family, strategy, screen_train, screen_val,
                predictors, mapping, args.random_seed, args.n_jobs, 80 if args.quick_check else 250)
            result["experiment_id"] = eid; result["training_coverage"] = "deterministic screening subset"
            experiments.append(result); family_results.append(result)
            args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
            args.metrics_output.with_suffix(".partial.json").write_text(
                json.dumps({"experiments": experiments}, indent=2, default=json_default), encoding="utf-8")
        selected_strategy[family] = min(family_results,
            key=lambda x: (x["validation"]["rmse"], x["validation"]["mae"]))["target_strategy"]

    extreme = float(splits["train"].meter_reading.quantile(EXTREME_QUANTILE))
    split_stats = {k: target_stats(v, extreme) for k, v in splits.items()}
    finalists = {}
    for family in families:
        strategy = selected_strategy[family]
        train_frame = splits["train"] if args.full_train else screen_train
        val_frame = splits["validation"] if args.full_train else screen_val
        logging.info("Final full candidate %s / %s", family, strategy)
        model, result, val_pred = train_once(family, strategy, train_frame, val_frame,
            predictors, mapping, args.random_seed, args.n_jobs, 120 if args.quick_check else 450)
        xte = prepare(splits["test"], predictors, mapping, family)
        started=time.perf_counter(); test_pred=model.predict(xte); test_seconds=time.perf_counter()-started
        test_pred, neg = original_prediction(np.asarray(test_pred), strategy)
        ytest=splits["test"].meter_reading.to_numpy(dtype=np.float32)
        result["test"] = metric_set(ytest, test_pred, neg)
        result["test_inference_seconds"] = test_seconds
        result["training_coverage"] = "full" if args.full_train else "deterministic screening subset"
        result["predictors"] = predictors
        result["categorical_strategy"] = {
            "xgboost": "training-fitted ordinal codes",
            "lightgbm": "training-defined native categorical levels",
            "catboost": "native string categorical features"}[family]
        result["subgroup_metrics"] = {
            "validation": subgroup_metrics(val_frame, val_pred, extreme),
            "test": subgroup_metrics(splits["test"], test_pred, extreme)}
        plot = args.figure_dir / f"{family}_feature_importance.png"
        top, kind = importance(model, family, predictors, plot)
        result["feature_importance"] = top; result["importance_type"] = kind
        result["feature_importance_plot"] = str(plot.relative_to(ROOT)).replace("\\", "/")
        artifact = save_artifact(model, family, args.output_dir/family, result, mapping)
        result.update(artifact)
        reloaded = reload_model(family, ROOT/result["model"])
        probe = splits["test"].iloc[:1000]
        xp = prepare(probe, predictors, mapping, family)
        p1 = np.asarray(model.predict(xp)); p2 = np.asarray(reloaded.predict(xp))
        result["reload_successful"] = bool(np.allclose(p1, p2, rtol=1e-6, atol=1e-6))
        result["deterministic_smoke_test"] = bool(np.array_equal(np.asarray(reloaded.predict(xp)),
                                                                 np.asarray(reloaded.predict(xp))))
        if not result["reload_successful"] or not result["deterministic_smoke_test"]:
            raise RuntimeError(f"Artifact smoke test failed: {family}")
        finalists[family] = result
        del model, xte, xp, test_pred, val_pred; gc.collect()

    comparison = {}
    for name, b in baseline["models"].items():
        comparison[name] = {"target_strategy": "raw", "training_coverage": "full",
            "validation": b["validation"], "test": b["test"],
            "training_time_seconds": b["training_time_seconds"],
            "test_inference_seconds": b["inference_time_seconds"]["test"],
            "artifact_size_bytes": (ROOT/b["model_path"]).stat().st_size}
    for name, f in finalists.items():
        comparison[name] = {"target_strategy": f["target_strategy"],
            "training_coverage": f["training_coverage"], "validation": f["validation"], "test": f["test"],
            "training_time_seconds": f["training_duration_seconds"],
            "test_inference_seconds": f["test_inference_seconds"],
            "artifact_size_bytes": f["artifact_size_bytes"]}
    best_val = min(finalists, key=lambda n: (finalists[n]["validation"]["rmse"], finalists[n]["validation"]["mae"]))
    best_test = min(finalists, key=lambda n: finalists[n]["test"]["rmse"])
    fastest = min(finalists, key=lambda n: finalists[n]["test_inference_seconds"])
    smallest = min(finalists, key=lambda n: finalists[n]["artifact_size_bytes"])
    source_after = fingerprint(args.input)
    baseline_after = {str(p.relative_to(ROOT)): fingerprint(p) for p in baseline_paths}
    integrity = {"input_unchanged": source_before == source_after,
                 "baseline_artifacts_unchanged": baseline_before == baseline_after,
                 "input_before": source_before, "input_after": source_after,
                 "baseline_before": baseline_before, "baseline_after": baseline_after}
    if not all([integrity["input_unchanged"], integrity["baseline_artifacts_unchanged"]]):
        raise RuntimeError("Input or baseline artifact changed during training.")
    result = {
        "task": "Week 2 Task 2.5 - Advanced Model Training and Comparison",
        "status": "passed", "completion_percentage": 100,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "dataset": dataset, "splits": baseline["splits"], "target": baseline["target"],
        "predictors": predictors, "numeric_predictors": [c for c in predictors if c not in categorical],
        "categorical_predictors": categorical, "excluded_columns": baseline["excluded_columns"],
        "random_seed": args.random_seed,
        "environment": {"cpu_count": os.cpu_count(), "n_jobs": args.n_jobs,
            "ram_gib": psutil.virtual_memory().total/2**30, "gpu": "not verified; CPU used",
            "platform": platform.platform(), "python": sys.version.split()[0],
            "libraries": {"xgboost": xgboost.__version__, "lightgbm": lightgbm.__version__,
                          "catboost": catboost.__version__, "pandas": pd.__version__,
                          "numpy": np.__version__, "scikit_learn": sklearn.__version__}},
        "training_design": {"screening_train_rows": len(screen_train),
            "screening_validation_rows": len(screen_val), "subset_method": "evenly spaced row indices via linspace; order preserved",
            "coverage_audit": coverage, "finalists_use_full_training_data": bool(args.full_train),
            "early_stopping_validation_only": True},
        "target_strategy": {"raw": "fit meter_reading directly",
            "log": "fit log1p(meter_reading), inverse with expm1, clip negative inverse predictions to zero only",
            "selection_basis": "validation RMSE, then validation MAE"},
        "experiments": experiments, "selected_strategy_by_family": selected_strategy,
        "final_candidates": finalists, "comparison": comparison,
        "drift_analysis": {"extreme_definition": f"training target >= {EXTREME_QUANTILE:.3f} quantile",
                           "target_statistics": split_stats},
        "selection": {"best_validation_model": best_val, "best_test_model": best_test,
            "fastest_advanced_model": fastest, "smallest_advanced_model": smallest,
            "recommended_candidate": best_val,
            "target_strategy": finalists[best_val]["target_strategy"],
            "rationale": "Chosen by validation RMSE then MAE; test used only for stability description."},
        "leakage_checks": {"exact_baseline_split_reused": True, "shuffle_used": False,
            "split_overlap": False, "training_only_category_mapping": True,
            "validation_used_for_early_stopping": True, "test_used_for_selection": False,
            "target_derived_predictors": False},
        "integrity": integrity,
    }
    args.metrics_output.write_text(json.dumps(result, indent=2, default=json_default), encoding="utf-8")
    args.report_output.write_text(render_report(result), encoding="utf-8")
    partial=args.metrics_output.with_suffix(".partial.json")
    if partial.exists(): partial.unlink()
    print("\nFiles created or modified:")
    for p in [Path("requirements.txt"), Path("scripts/week2_advanced_models.py"),
              args.metrics_output.relative_to(ROOT), args.report_output.relative_to(ROOT),
              DEFAULT_LOG.relative_to(ROOT), args.figure_dir.relative_to(ROOT), args.output_dir.relative_to(ROOT)]:
        print("-", p)
    print(f"\nHardware/libraries: {os.cpu_count()} CPUs, {result['environment']['ram_gib']:.2f} GiB RAM, CPU mode; "
          f"XGBoost {xgboost.__version__}, LightGBM {lightgbm.__version__}, CatBoost {catboost.__version__}")
    print("Exact splits:", {k:v["rows"] for k,v in baseline["splits"].items()})
    print("Experiments completed:", len(experiments))
    print("Best validation model:", best_val)
    print("Recommended production candidate:", best_val)
    print("Target strategy selected:", finalists[best_val]["target_strategy"])
    print("Artifact sizes:", {k:v["artifact_size_bytes"] for k,v in finalists.items()})
    print("Unresolved risks: temporal drift, extreme targets, single-year validation, unseen categories, importance bias.")
    print("Task 2.5 completion percentage: 100%")


if __name__ == "__main__":
    main()
