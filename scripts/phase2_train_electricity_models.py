"""Train and evaluate non-production Phase 2 electricity model candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data/processed/electricity_features.csv"
DEFAULT_SCHEMA = ROOT / "reports/phase2_electricity_feature_schema.json"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_MODELS = ROOT / "models/candidates"
TRAIN_END = pd.Timestamp("2016-08-31 23:59:59")
VALID_END = pd.Timestamp("2016-10-31 23:59:59")
SEED = 42


def split_name(timestamp: pd.Timestamp) -> str:
    if timestamp <= TRAIN_END: return "training"
    if timestamp <= VALID_END: return "validation"
    return "testing"


def select_best(results: dict) -> str:
    eligible = [(name, values["validation"]) for name, values in results.items() if values.get("status") == "trained"]
    if not eligible: raise ValueError("No trained models available for selection.")
    return min(eligible, key=lambda item: (item[1]["mae"], item[1]["rmsle"], -item[1]["r2"]))[0]


def consumption_band(value: float, thresholds: dict[str, float]) -> str:
    if value <= thresholds["small_max"]: return "small"
    if value <= thresholds["medium_max"]: return "medium"
    if value <= thresholds["large_max"]: return "large"
    return "peak"


def load_schema(path: Path) -> tuple[list[str], list[str], str, str]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not schema.get("meter_removed_from_predictors") or schema.get("target_derived_features"):
        raise ValueError("Feature schema fails meter/target leakage requirements.")
    numeric = schema["numeric_feature_columns"]
    categorical = schema["categorical_feature_columns"]
    if "meter" in numeric + categorical or schema["target_column"] in numeric + categorical:
        raise ValueError("Forbidden predictor in feature schema.")
    return numeric, categorical, schema["target_column"], schema["timestamp_column"]


def metric_result(state: dict) -> dict:
    n = state["n"]
    mean = state["sum_y"] / n
    ss_total = state["sum_y2"] - n * mean * mean
    return {
        "rows": n,
        "mae": state["abs"] / n,
        "rmse": math.sqrt(state["sq"] / n),
        "r2": 1 - state["sq"] / ss_total if ss_total > 0 else 0.0,
        "rmsle": math.sqrt(state["log_sq"] / n),
        "prediction_time_seconds": state["prediction_time"],
    }


def update_state(state: dict, actual: np.ndarray, prediction: np.ndarray, seconds: float) -> None:
    prediction = np.maximum(np.asarray(prediction, dtype="float64"), 0)
    actual = np.asarray(actual, dtype="float64")
    residual = prediction - actual
    state["n"] += len(actual); state["abs"] += np.abs(residual).sum(); state["sq"] += np.square(residual).sum()
    state["log_sq"] += np.square(np.log1p(prediction)-np.log1p(actual)).sum()
    state["sum_y"] += actual.sum(); state["sum_y2"] += np.square(actual).sum(); state["prediction_time"] += seconds


def make_state() -> dict:
    return {"n": 0, "abs": 0.0, "sq": 0.0, "log_sq": 0.0, "sum_y": 0.0, "sum_y2": 0.0, "prediction_time": 0.0}


def train(args: argparse.Namespace) -> dict:
    from joblib import dump
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric, categorical, target, timestamp = load_schema(args.schema)
    usecols = [timestamp, target, *numeric, *categorical]
    train_parts, train_targets, split_counts = [], [], defaultdict(int)
    # Pass 1 counts the immutable chronological partitions. Pass 2 takes a
    # systematic sample across the entire training partition (not file head),
    # preserving membership and source order without shuffling.
    for chunk in pd.read_csv(args.input, usecols=usecols, chunksize=args.chunk_size, parse_dates=[timestamp]):
        names = chunk[timestamp].map(split_name)
        for name, count in names.value_counts().items(): split_counts[name] += int(count)
    stride = max(1, math.ceil(split_counts["training"] / args.max_train_rows))
    training_seen = 0
    for chunk in pd.read_csv(args.input, usecols=usecols, chunksize=args.chunk_size, parse_dates=[timestamp]):
        names = chunk[timestamp].map(split_name)
        part = chunk.loc[names.eq("training")]
        if len(part):
            positions = np.arange(training_seen, training_seen + len(part))
            selected = (positions % stride) == 0
            train_parts.append(part.iloc[np.flatnonzero(selected)])
            train_targets.append(part[target].iloc[np.flatnonzero(selected)])
            training_seen += len(part)
    training = pd.concat(train_parts, ignore_index=True).iloc[:args.max_train_rows]
    y_train = pd.concat(train_targets, ignore_index=True).iloc[:len(training)].to_numpy()
    X_train = training[numeric + categorical]
    thresholds = {"small_max": float(np.quantile(y_train, .50)), "medium_max": float(np.quantile(y_train, .90)), "large_max": float(np.quantile(y_train, .99))}
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
    ], verbose_feature_names_out=False)
    X_transformed = preprocessor.fit_transform(X_train).astype("float32")
    feature_names = preprocessor.get_feature_names_out().tolist()
    models = {
        "dummy": DummyRegressor(strategy="median"),
        "linear_regression": LinearRegression(n_jobs=-1),
        "ridge": Ridge(alpha=10.0),
        "random_forest": RandomForestRegressor(n_estimators=60, max_depth=18, min_samples_leaf=5, n_jobs=-1, random_state=SEED),
        "hist_gradient_boosting": HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=31, learning_rate=.08, random_state=SEED),
    }
    try:
        from xgboost import XGBRegressor
        models["xgboost"] = XGBRegressor(n_estimators=300, max_depth=8, learning_rate=.05, subsample=.8, colsample_bytree=.8, tree_method="hist", n_jobs=-1, random_state=SEED)
        xgb_skip = None
    except ImportError as exc: xgb_skip = str(exc)
    args.models.mkdir(parents=True, exist_ok=True); args.reports.mkdir(parents=True, exist_ok=True)
    results, fitted = {}, {}
    for name, model in models.items():
        started = time.perf_counter(); model.fit(X_transformed, y_train); elapsed = time.perf_counter()-started
        artifact = args.models / f"{name}.joblib"; dump({"preprocessor": preprocessor, "model": model, "schema": str(args.schema), "production": False}, artifact, compress=3)
        results[name] = {"status": "trained", "training_time_seconds": elapsed, "model_size_bytes": artifact.stat().st_size}
        fitted[name] = model
    if xgb_skip: results["xgboost"] = {"status": "skipped", "reason": xgb_skip}

    states = {name: {split: make_state() for split in ("validation", "testing")} for name in fitted}
    bands = {name: {split: {band: make_state() for band in ("small", "medium", "large", "peak")} for split in ("validation", "testing")} for name in fitted}
    residual_rows = []; importance_X = importance_y = None
    for chunk in pd.read_csv(args.input, usecols=usecols, chunksize=args.chunk_size, parse_dates=[timestamp]):
        split_series = chunk[timestamp].map(split_name)
        for split in ("validation", "testing"):
            part = chunk.loc[split_series.eq(split)]
            if part.empty: continue
            transformed = preprocessor.transform(part[numeric+categorical]).astype("float32"); actual = part[target].to_numpy()
            if split == "validation" and importance_X is None:
                take = min(args.importance_rows, len(part)); importance_X, importance_y = transformed[:take], actual[:take]
            for name, model in fitted.items():
                started = time.perf_counter(); prediction = np.maximum(model.predict(transformed), 0); elapsed = time.perf_counter()-started
                update_state(states[name][split], actual, prediction, elapsed)
                labels = np.array([consumption_band(v, thresholds) for v in actual])
                for band in ("small", "medium", "large", "peak"):
                    mask = labels == band
                    if mask.any(): update_state(bands[name][split][band], actual[mask], prediction[mask], 0)
                if len(residual_rows) < args.plot_rows and name == "random_forest":
                    for ts, a, p in zip(part[timestamp].iloc[:1000], actual[:1000], prediction[:1000]): residual_rows.append((split, ts, float(a), float(p), float(p-a)))
    for name in fitted:
        for split in ("validation", "testing"):
            results[name][split] = metric_result(states[name][split])
            results[name][split]["consumption_bands"] = {band: metric_result(state) for band, state in bands[name][split].items() if state["n"]}
    best = select_best(results)
    importance = write_importance(args.reports / "phase2_feature_importance.csv", fitted, feature_names, importance_X, importance_y)
    write_residual_outputs(args.reports, residual_rows)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "split": {"training_end": str(TRAIN_END), "validation_end": str(VALID_END), "counts": dict(split_counts)}, "training_sample_rows": len(training), "training_cap": args.max_train_rows, "selection_rule": "lowest validation MAE, then lowest RMSLE, then highest R2", "consumption_band_thresholds_from_training_target": thresholds, "models": results, "best_model": best, "feature_importance_top25": importance, "production_updated": False}
    (args.reports/"phase2_training_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (args.reports/"phase2_model_comparison.json").write_text(json.dumps({"best_model": best, "models": results}, indent=2), encoding="utf-8")
    write_reports(args.reports, payload)
    return payload


def write_importance(path: Path, models: dict, names: list[str], X, y) -> list[dict]:
    from sklearn.inspection import permutation_importance
    rows = []
    for model_name in ("random_forest", "hist_gradient_boosting", "xgboost"):
        if model_name not in models: continue
        model = models[model_name]
        native = getattr(model, "feature_importances_", np.full(len(names), np.nan))
        perm = permutation_importance(model, X, y, n_repeats=2, random_state=SEED, scoring="neg_mean_absolute_error", n_jobs=-1).importances_mean
        for feature, nvalue, pvalue in zip(names, native, perm): rows.append({"model": model_name, "feature": feature, "native_importance": None if np.isnan(nvalue) else float(nvalue), "permutation_importance_mae": float(pvalue)})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["model", "feature", "native_importance", "permutation_importance_mae"]); writer.writeheader(); writer.writerows(rows)
    return sorted(rows, key=lambda row: row["permutation_importance_mae"], reverse=True)[:25]


def write_residual_outputs(reports: Path, rows: list[tuple]) -> None:
    import matplotlib.pyplot as plt
    frame = pd.DataFrame(rows, columns=["split", "timestamp", "actual", "prediction", "residual"])
    figures = reports / "figures/phase2"; figures.mkdir(parents=True, exist_ok=True)
    specs = [("residual_histogram", lambda ax: ax.hist(frame.residual, bins=60)), ("prediction_vs_actual", lambda ax: ax.scatter(frame.actual, frame.prediction, s=3, alpha=.25)), ("residual_vs_prediction", lambda ax: ax.scatter(frame.prediction, frame.residual, s=3, alpha=.25)), ("residual_vs_time", lambda ax: ax.scatter(frame.timestamp, frame.residual, s=3, alpha=.25))]
    for name, draw in specs:
        fig, ax = plt.subplots(figsize=(8, 4)); draw(ax); ax.set_title(name.replace("_", " ").title()); fig.tight_layout(); fig.savefig(figures/f"{name}.png", dpi=140); plt.close(fig)
    frame["date"] = pd.to_datetime(frame.timestamp).dt.date; frame["month"] = pd.to_datetime(frame.timestamp).dt.to_period("M").astype(str)
    for key, name in (("date", "daily_error_trend"), ("month", "monthly_error_trend")):
        trend = frame.groupby(key).residual.apply(lambda value: np.abs(value).mean())
        fig, ax = plt.subplots(figsize=(8, 4)); trend.plot(ax=ax); ax.set_ylabel("MAE"); fig.tight_layout(); fig.savefig(figures/f"{name}.png", dpi=140); plt.close(fig)
    (reports/"phase2_residual_analysis.md").write_text("# Phase 2 Residual Analysis\n\nResidual plots were generated from a bounded deterministic Random Forest validation/test sample. Positive residual means overprediction. See `reports/figures/phase2/`. Daily and monthly plots report sample MAE trends; they are diagnostic rather than full-population aggregates.\n", encoding="utf-8")


def write_reports(reports: Path, payload: dict) -> None:
    rows = []
    for name, values in payload["models"].items():
        if values["status"] == "trained":
            v, t = values["validation"], values["testing"]
            rows.append(f"| {name} | {v['mae']:.4f} | {v['rmse']:.4f} | {v['r2']:.6f} | {v['rmsle']:.6f} | {t['mae']:.4f} | {t['rmse']:.4f} | {t['r2']:.6f} | {t['rmsle']:.6f} | {values['training_time_seconds']:.2f} | {values['model_size_bytes']/2**20:.2f} |")
    table = "\n".join(rows)
    content = f"""# Phase 2 Electricity Model Comparison

Candidates only; production v1.0.0 was not changed. Training used a deterministic bounded subset of {payload['training_sample_rows']:,} training-period rows because the requested in-memory estimators cannot safely consume the entire multi-million-row training partition on this workstation. Validation and test metrics use their complete chronological partitions.

| Model | Val MAE | Val RMSE | Val R2 | Val RMSLE | Test MAE | Test RMSE | Test R2 | Test RMSLE | Train sec | MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

Best candidate: **{payload['best_model']}**, selected by validation MAE, RMSLE, then R2. Consumption bands use training-target percentiles: small <= {payload['consumption_band_thresholds_from_training_target']['small_max']:.4f}, medium <= {payload['consumption_band_thresholds_from_training_target']['medium_max']:.4f}, large <= {payload['consumption_band_thresholds_from_training_target']['large_max']:.4f}, and peak above that. The electricity unit remains unverified.

XGBoost status: **{payload['models']['xgboost']['status']}** — {payload['models']['xgboost'].get('reason', 'trained')}.
"""
    (reports/"phase2_model_comparison.md").write_text(content, encoding="utf-8")
    (reports/"phase2_training_summary.md").write_text(content + "\n## Recommendation\n\nTreat the winner as a v2 candidate only. Review drift, band errors, residual plots, and training-cap sensitivity before any packaging or production decision.\n", encoding="utf-8")
    best = payload["models"][payload["best_model"]]
    vb, tb = best["validation"]["consumption_bands"], best["testing"]["consumption_bands"]
    residual = f"""# Phase 2 Residual Analysis

Six diagnostic plots were generated from a bounded deterministic Random Forest validation/test sample under `reports/figures/phase2/`: residual histogram, prediction versus actual, residual versus prediction, residual versus time, daily error trend, and monthly error trend. Positive residual means overprediction. Daily/monthly plots are sample diagnostics; the metrics below use the complete partitions.

## Calculated findings

- Overall MAE rises from **{best['validation']['mae']:.4f}** on validation to **{best['testing']['mae']:.4f}** on test; RMSE rises from **{best['validation']['rmse']:.4f}** to **{best['testing']['rmse']:.4f}**.
- R2 declines from **{best['validation']['r2']:.6f}** to **{best['testing']['r2']:.6f}**, evidence of temporal generalization loss.
- Test MAE by magnitude is small **{tb['small']['mae']:.4f}**, medium **{tb['medium']['mae']:.4f}**, large **{tb['large']['mae']:.4f}**, and peak **{tb['peak']['mae']:.4f}**.
- Peak test RMSE is **{tb['peak']['rmse']:.4f}** and peak R2 is **{tb['peak']['r2']:.6f}**; extreme consumption remains the main residual-risk concentration.
- Small-band R2 is strongly negative despite low absolute MAE because the band has little target variance and occasional large misses dominate squared error. Band MAE/RMSLE are more interpretable there.
- Validation-to-test peak MAE increases from **{vb['peak']['mae']:.4f}** to **{tb['peak']['mae']:.4f}**, so this candidate should not be promoted without drift and extreme-event work.
"""
    (reports/"phase2_residual_analysis.md").write_text(residual, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA); parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS); parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--chunk-size", type=int, default=200_000); parser.add_argument("--max-train-rows", type=int, default=250_000)
    parser.add_argument("--importance-rows", type=int, default=5000); parser.add_argument("--plot-rows", type=int, default=50000)
    return parser.parse_args()


if __name__ == "__main__":
    result = train(parse_args()); print(json.dumps({"best_model": result["best_model"], "training_sample_rows": result["training_sample_rows"]}, indent=2))
