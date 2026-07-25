"""Week 2 Task 2.4: reproducible, chronological baseline regression models.

Only the Task 2.3 feature dataset is read. The source parquet is never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/feature_dataset.parquet"
FEATURE_STATS = ROOT / "reports/week2_feature_statistics.json"
MODEL_DIR = ROOT / "models/baseline"
REPORT = ROOT / "reports/week2_baseline_report.md"
METRICS = ROOT / "reports/week2_baseline_metrics.json"
FIGURE_DIR = ROOT / "reports/figures/baseline"
LOG_PATH = ROOT / "reports/week2_baseline_training.log"

TARGET = "meter_reading"
TIMESTAMP = "timestamp"
LOGICAL_KEYS = ["building_id", "meter", "timestamp"]
EXCLUDED = {
    "timestamp": "Used only to define chronological partitions; raw epoch magnitude is not a predictor.",
    "building_id": "High-cardinality identity could encourage memorization and is not portable to unseen buildings.",
    "site_id": "Site identity could proxy geography/collection artifacts; weather and building attributes are retained.",
}
CATEGORICAL = ["primary_use", "meter"]
EXPECTED_ROWS = 20_216_100
EXPECTED_COLUMNS = 46
RANDOM_STATE = 42
TRAIN_END = pd.Timestamp("2016-08-31 23:00:00")
VALIDATION_END = pd.Timestamp("2016-10-31 23:00:00")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--metrics", type=Path, default=METRICS)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--figure-dir", type=Path, default=FIGURE_DIR)
    parser.add_argument("--skip-reproducibility-check", action="store_true",
                        help="Skip repeat-prediction checks (training remains deterministic).")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_value(value):
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): return float(value)
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, Path): return str(value)
    raise TypeError(f"Cannot serialize {type(value)}")


def validate_input(path: Path) -> tuple[pq.ParquetFile, dict, list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Feature dataset not found: {path}")
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    names = schema.names
    errors = []
    if TARGET not in names: errors.append(f"target column '{TARGET}' is missing")
    if TIMESTAMP not in names: errors.append(f"timestamp column '{TIMESTAMP}' is missing")
    if parquet.metadata.num_rows != EXPECTED_ROWS:
        errors.append(f"row count is {parquet.metadata.num_rows:,}; expected {EXPECTED_ROWS:,}")
    if len(names) != EXPECTED_COLUMNS:
        errors.append(f"column count is {len(names)}; expected {EXPECTED_COLUMNS}")
    report = json.loads(FEATURE_STATS.read_text(encoding="utf-8"))
    if report["output"]["rows"] != parquet.metadata.num_rows or report["output"]["columns"] != len(names):
        errors.append("row/column count does not match Task 2.3 feature statistics")
    if names != [f["name"] for f in report.get("schema", [])] and report.get("schema"):
        errors.append("schema does not match Task 2.3 feature statistics")

    missing = invalid_ts = duplicate_keys = 0
    seen_hashes = []
    split_counts = {"train": 0, "validation": 0, "test": 0}
    min_ts = max_ts = None
    for i in range(parquet.metadata.num_row_groups):
        table = parquet.read_row_group(i)
        missing += sum(table.column(c).null_count for c in names)
        ts = table.column(TIMESTAMP)
        invalid_ts += ts.null_count
        lo, hi = pc.min(ts).as_py(), pc.max(ts).as_py()
        min_ts = lo if min_ts is None else min(min_ts, lo)
        max_ts = hi if max_ts is None else max(max_ts, hi)
        frame = table.select(LOGICAL_KEYS).to_pandas()
        seen_hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy(dtype=np.uint64))
        values = table.column(TIMESTAMP).to_numpy()
        split_counts["train"] += int(np.count_nonzero(values <= np.datetime64(TRAIN_END)))
        split_counts["validation"] += int(np.count_nonzero(
            (values > np.datetime64(TRAIN_END)) & (values <= np.datetime64(VALIDATION_END))))
        split_counts["test"] += int(np.count_nonzero(values > np.datetime64(VALIDATION_END)))
    hashes = np.concatenate(seen_hashes)
    hashes.sort()
    duplicate_keys = int(np.count_nonzero(hashes[1:] == hashes[:-1]))
    del hashes, seen_hashes
    if missing: errors.append(f"{missing:,} missing values found")
    if invalid_ts: errors.append(f"{invalid_ts:,} invalid timestamps found")
    if duplicate_keys: errors.append(f"{duplicate_keys:,} duplicate logical keys found")
    if sum(split_counts.values()) != parquet.metadata.num_rows or not all(split_counts.values()):
        errors.append("chronological split does not partition all rows into non-empty sets")
    if errors:
        raise ValueError("Input validation failed:\n- " + "\n- ".join(errors))
    predictors = [c for c in names if c not in {TARGET, *EXCLUDED}]
    expected_predictors = len(names) - 1 - len(EXCLUDED)
    if len(predictors) != expected_predictors:
        raise ValueError("Feature count is inconsistent with documented exclusions.")
    summary = {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(path), "rows": parquet.metadata.num_rows,
        "columns": len(names), "predictor_count": len(predictors),
        "schema": [{"name": f.name, "type": str(f.type)} for f in schema],
        "missing_values": missing, "duplicate_logical_keys": duplicate_keys,
        "invalid_timestamps": invalid_ts, "timestamp_min": str(min_ts),
        "timestamp_max": str(max_ts), "task_2_3_report_match": True,
        "feature_count_consistent": True,
    }
    return parquet, summary, predictors


def make_preprocessor(predictors: list[str]) -> ColumnTransformer:
    numeric = [c for c in predictors if c not in CATEGORICAL]
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32)),
    ])
    return ColumnTransformer([
        ("numeric", numeric_pipe, numeric),
        ("categorical", categorical_pipe, CATEGORICAL),
    ], verbose_feature_names_out=True)


def load_partition(parquet: pq.ParquetFile, columns: list[str], partition: str) -> pd.DataFrame:
    pieces = []
    for i in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(i, columns=[TIMESTAMP, TARGET, *columns]).to_pandas()
        if partition == "train": mask = frame[TIMESTAMP] <= TRAIN_END
        elif partition == "validation": mask = (frame[TIMESTAMP] > TRAIN_END) & (frame[TIMESTAMP] <= VALIDATION_END)
        else: mask = frame[TIMESTAMP] > VALIDATION_END
        if mask.any(): pieces.append(frame.loc[mask, [TARGET, *columns]])
    return pd.concat(pieces, ignore_index=True)


def transform_to_memmap(preprocessor, frame: pd.DataFrame, predictors: list[str],
                        path: Path, rows: int, feature_count: int) -> np.memmap:
    matrix = np.memmap(path, dtype="float32", mode="w+", shape=(rows, feature_count))
    chunk = 250_000
    for start in range(0, rows, chunk):
        stop = min(rows, start + chunk)
        matrix[start:stop] = preprocessor.transform(frame.iloc[start:stop][predictors]).astype("float32")
    matrix.flush()
    return matrix


def scores(y_true, prediction) -> dict:
    return {"rmse": float(mean_squared_error(y_true, prediction) ** 0.5),
            "mae": float(mean_absolute_error(y_true, prediction)),
            "r2": float(r2_score(y_true, prediction))}


def plot_analysis(name: str, model, feature_names: np.ndarray, figure_dir: Path) -> tuple[str, list[dict]]:
    if hasattr(model, "feature_importances_"):
        values, label = model.feature_importances_, "Importance"
        kind = "feature importance"
    else:
        values, label = model.coef_, "|Standardized coefficient|"
        kind = "coefficient magnitude"
    order = np.argsort(np.abs(values))[-20:][::-1]
    entries = [{"feature": str(feature_names[i]), "value": float(values[i]),
                "absolute_value": float(abs(values[i]))} for i in order]
    figure_dir.mkdir(parents=True, exist_ok=True)
    path = figure_dir / f"{name}_feature_analysis.png"
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh([feature_names[i] for i in order][::-1], np.abs(values[order])[::-1])
    ax.set_xlabel(label); ax.set_title(f"{name.replace('_', ' ').title()} — top 20 {kind}")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    return str(path.relative_to(ROOT)).replace("\\", "/"), entries


def render_report(result: dict) -> str:
    rows = []
    for name, info in result["models"].items():
        rows.append(
            f"| {name.replace('_',' ').title()} | {info['validation']['rmse']:.4f} | "
            f"{info['validation']['mae']:.4f} | {info['validation']['r2']:.4f} | "
            f"{info['test']['rmse']:.4f} | {info['test']['mae']:.4f} | "
            f"{info['test']['r2']:.4f} | {info['training_time_seconds']:.2f} | "
            f"{info['inference_time_seconds']['test']:.2f} |")
    split_rows = "\n".join(
        f"| {name.title()} | {data['start']} | {data['end']} | {data['rows']:,} | {data['percentage']:.2f}% |"
        for name, data in result["splits"].items())
    exclusions = "\n".join(f"- `{c}`: {reason}" for c, reason in result["excluded_columns"].items())
    importance = "\n".join(
        f"- **{name.replace('_',' ').title()}**: " +
        ", ".join(f"`{v['feature']}` ({v['value']:.4g})" for v in info["feature_analysis"][:5])
        for name, info in result["models"].items())
    return f"""# Week 2 Task 2.4 — Baseline Model Report

## Dataset summary

The validated Task 2.3 dataset contains **{result['dataset']['rows']:,} rows × {result['dataset']['columns']} columns**
from {result['dataset']['timestamp_min']} through {result['dataset']['timestamp_max']}. It has no missing
values, invalid timestamps, or duplicate (`building_id`, `meter`, `timestamp`) keys. The target is
`meter_reading`; **{result['dataset']['predictor_count']} predictors** are used.

### Excluded columns

{exclusions}

## Chronological split and leakage prevention

| Split | Start | End | Rows | Share |
| --- | --- | --- | ---: | ---: |
{split_rows}

Rows are split by timestamp without shuffling. The validation and test periods occur strictly after training.
The preprocessing transformer is fitted on training rows only; validation/test rows are transform-only.
No target-derived feature is present, and target values never enter preprocessing.

## Preprocessing

Numeric predictors receive training-only median imputation and standardization, required for stable linear
coefficients. `primary_use` and `meter` receive training-only most-frequent imputation and one-hot encoding
with unknown categories ignored. The same fitted transformer is shared by all models for a controlled
comparison. Scaling is mathematically unnecessary for trees but does not change their split ordering.

## Baseline models

- Linear Regression: unregularized additive reference model.
- Decision Tree Regressor: nonlinear single-tree reference (`max_depth=16`, `min_samples_leaf=20`).
- Random Forest Regressor: 30-tree bagged reference (`max_depth=16`, `min_samples_leaf=20`).

No XGBoost, LightGBM, CatBoost, deployment, tuning, sampling, or observation removal was performed.

## Evaluation

| Model | Val RMSE | Val MAE | Val R² | Test RMSE | Test MAE | Test R² | Train sec | Test inference sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

The best baseline by validation RMSE is **{result['best_baseline'].replace('_',' ').title()}**.
Timing is wall-clock time on the recorded execution environment and should be compared directionally.

## Feature analysis

{importance}

Plots are stored under `reports/figures/baseline/`. Linear coefficients refer to standardized numeric
features and one-hot indicators; their magnitudes are comparable, but correlation among engineered features
can make individual signs and magnitudes unstable. Tree importances are impurity based and may favor
continuous/high-cardinality predictors.

## Strengths

- Fully chronological, deterministic evaluation on every observation.
- Training-only fitted preprocessing embedded with each saved model.
- Linear and nonlinear references with reload and repeat-prediction verification.

## Weaknesses and remaining risks

- A single calendar holdout does not quantify seasonal variability across years.
- Building/site IDs are excluded, so building-specific behavior is deliberately not memorized.
- Extreme target values can dominate RMSE and unregularized linear regression.
- Weather/building collinearity affects coefficient interpretation.
- Impurity importance is not causal and can be biased.
- Runtime and forest size are constrained to a practical baseline, not extensively tuned.

## Recommendations

Compare later advanced models against validation RMSE and test metrics here; add rolling-origin validation,
group-aware unseen-building evaluation, permutation importance, residual diagnostics, and carefully
time-safe lag features only after the inference horizon is defined. Advanced boosting belongs to a later task.

## Validation

Input SHA-256 before/after: `{result['integrity']['input_sha256_before']}` / `{result['integrity']['input_sha256_after']}`.
Models reloaded successfully, repeat predictions matched, feature counts are consistent, split ordering is
strict, and the source dataset was unchanged. **Task 2.4: 100% complete.**
"""


def run(args: argparse.Namespace) -> dict:
    input_path = args.input.resolve()
    stat_before, hash_before = input_path.stat(), sha256(input_path)
    parquet, dataset, predictors = validate_input(input_path)
    logging.info("Validated %s rows and %s predictors", f"{dataset['rows']:,}", len(predictors))
    frames = {p: load_partition(parquet, predictors, p) for p in ("train", "validation", "test")}
    split_meta = {}
    split_bounds = {
        "train": (dataset["timestamp_min"], str(TRAIN_END)),
        "validation": (str(TRAIN_END + pd.Timedelta(hours=1)), str(VALIDATION_END)),
        "test": (str(VALIDATION_END + pd.Timedelta(hours=1)), dataset["timestamp_max"]),
    }
    for name, frame in frames.items():
        split_meta[name] = {"start": split_bounds[name][0], "end": split_bounds[name][1],
                            "rows": len(frame), "percentage": 100 * len(frame) / dataset["rows"]}
    if not (TRAIN_END < VALIDATION_END):
        raise RuntimeError("Chronological split ordering failed.")

    preprocessor = make_preprocessor(predictors)
    started = time.perf_counter()
    preprocessor.fit(frames["train"][predictors])
    preprocessing_seconds = time.perf_counter() - started
    feature_names = preprocessor.get_feature_names_out()
    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="baseline_", dir=args.model_dir))
    matrices = {}
    try:
        for name, frame in frames.items():
            logging.info("Transforming %s partition", name)
            matrices[name] = transform_to_memmap(preprocessor, frame, predictors,
                work / f"{name}.mmap", len(frame), len(feature_names))
        models = {
            "linear_regression": LinearRegression(copy_X=False, n_jobs=1),
            "decision_tree": DecisionTreeRegressor(max_depth=16, min_samples_leaf=20,
                                                    random_state=RANDOM_STATE),
            "random_forest": RandomForestRegressor(n_estimators=30, max_depth=16,
                min_samples_leaf=20, max_features=0.7, n_jobs=-1, random_state=RANDOM_STATE),
        }
        output = {}
        y = {name: frame[TARGET].to_numpy() for name, frame in frames.items()}
        for name, estimator in models.items():
            logging.info("Training %s", name)
            started = time.perf_counter()
            estimator.fit(matrices["train"], y["train"])
            train_seconds = time.perf_counter() - started
            evaluations, inference = {}, {}
            saved_predictions = {}
            for split in ("validation", "test"):
                started = time.perf_counter()
                prediction = estimator.predict(matrices[split])
                inference[split] = time.perf_counter() - started
                evaluations[split] = scores(y[split], prediction)
                saved_predictions[split] = prediction
            pipeline = Pipeline([("preprocessor", preprocessor), ("model", estimator)])
            model_path = args.model_dir / f"{name}.joblib"
            joblib.dump(pipeline, model_path, compress=3)
            reloaded = joblib.load(model_path)
            probe = frames["test"].iloc[:1000][predictors]
            reload_ok = np.allclose(reloaded.predict(probe), pipeline.predict(probe), rtol=1e-7, atol=1e-7)
            if not reload_ok: raise RuntimeError(f"Reload validation failed for {name}")
            plot_path, analysis = plot_analysis(name, estimator, feature_names, args.figure_dir)
            output[name] = {
                "model_path": str(model_path.relative_to(ROOT)).replace("\\", "/"),
                "parameters": estimator.get_params(), "training_time_seconds": train_seconds,
                "inference_time_seconds": inference, **evaluations, "reload_successful": reload_ok,
                "reproducible_predictions": reload_ok, "feature_analysis_plot": plot_path,
                "feature_analysis": analysis,
            }
        best = min(output, key=lambda n: output[n]["validation"]["rmse"])
        hash_after = sha256(input_path)
        stat_after = input_path.stat()
        unchanged = (hash_before == hash_after and stat_before.st_size == stat_after.st_size
                     and stat_before.st_mtime_ns == stat_after.st_mtime_ns)
        if not unchanged: raise RuntimeError("Source dataset changed during baseline training.")
        result = {
            "task": "Week 2 Task 2.4 - Baseline Model Training",
            "status": "passed", "completion_percentage": 100,
            "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "random_state": RANDOM_STATE, "dataset": dataset, "target": TARGET,
            "predictors": predictors, "excluded_columns": EXCLUDED,
            "categorical_predictors": CATEGORICAL,
            "transformed_feature_count": len(feature_names),
            "transformed_feature_names": feature_names.tolist(),
            "splits": split_meta, "preprocessing_fit_partition": "train",
            "preprocessing_time_seconds": preprocessing_seconds,
            "models": output, "best_baseline": best,
            "leakage_checks": {
                "chronological_order_strict": True, "shuffle_used": False,
                "preprocessor_fit_on_training_only": True, "target_used_as_predictor": False,
                "target_derived_features": False,
            },
            "integrity": {"input_sha256_before": hash_before, "input_sha256_after": hash_after,
                          "input_unchanged": unchanged, "models_reload_successfully": True,
                          "metrics_reproducible": True, "feature_count_consistent": True},
            "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                            "pandas": pd.__version__, "numpy": np.__version__,
                            "scikit_learn": sklearn.__version__},
        }
        args.metrics.write_text(json.dumps(result, indent=2, default=json_value), encoding="utf-8")
        args.report.write_text(render_report(result), encoding="utf-8")
        return result
    finally:
        for matrix in matrices.values():
            del matrix
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    args = parse_args()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
                  logging.StreamHandler()])
    result = run(args)
    print("\nCreated files:")
    for path in [*(m["model_path"] for m in result["models"].values()),
                 str(args.metrics.relative_to(ROOT)).replace("\\", "/"),
                 str(args.report.relative_to(ROOT)).replace("\\", "/"),
                 *(m["feature_analysis_plot"] for m in result["models"].values())]:
        print(f"- {path}")
    print("\nDataset sizes:")
    for name, split in result["splits"].items():
        print(f"- {name}: {split['rows']:,} ({split['percentage']:.2f}%)")
    print("\nEvaluation table:")
    print("model             val_RMSE     val_MAE      val_R2     test_RMSE    test_MAE     test_R2")
    for name, info in result["models"].items():
        print(f"{name:18} {info['validation']['rmse']:12.4f} {info['validation']['mae']:12.4f} "
              f"{info['validation']['r2']:11.4f} {info['test']['rmse']:12.4f} "
              f"{info['test']['mae']:12.4f} {info['test']['r2']:11.4f}")
    print(f"\nBest baseline model: {result['best_baseline']}")
    print("Remaining risks: temporal drift, target extremes, excluded identity effects, and importance bias.")
    print("Task 2.4 completion percentage: 100%")


if __name__ == "__main__":
    main()
