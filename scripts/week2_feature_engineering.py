"""Week 2 Task 2.3: deterministic, leakage-safe feature engineering.

The script reads the clean Parquet dataset in row groups, preserves every
original column and row, and never derives a feature from meter_reading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "clean_dataset.parquet"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "feature_dataset.parquet"
DEFAULT_METRICS = ROOT / "reports" / "week2_feature_statistics.json"
DEFAULT_REPORT = ROOT / "reports" / "week2_feature_report.md"
DEFAULT_NOTEBOOK = ROOT / "notebooks" / "04_feature_engineering.ipynb"
EXPECTED_ROWS = 20_216_100
KEY_COLUMNS = ["building_id", "meter", "timestamp"]
REQUIRED_COLUMNS = [
    "building_id", "meter", "timestamp", "meter_reading", "site_id",
    "primary_use", "square_feet", "year_built", "floor_count",
    "air_temperature", "cloud_coverage", "dew_temperature",
    "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
]
TIME_FEATURES = [
    "hour", "day_of_week", "day_of_month", "day_of_year", "week_of_year",
    "month", "quarter", "is_weekend", "hour_sin", "hour_cos",
    "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos",
]
BUILDING_FEATURES = ["building_age_2016", "log_square_feet", "square_feet_per_floor"]
WEATHER_FEATURES = [
    "temperature_difference", "relative_humidity", "wind_direction_sin",
    "wind_direction_cos", "is_precipitating", "is_freezing", "is_hot",
    "heating_degree_proxy", "cooling_degree_proxy",
]
INTERACTION_FEATURES = [
    "log_square_feet_x_air_temperature", "building_age_x_air_temperature",
    "heating_degree_x_log_square_feet", "cooling_degree_x_log_square_feet",
]
ENGINEERED_FEATURES = TIME_FEATURES + BUILDING_FEATURES + WEATHER_FEATURES + INTERACTION_FEATURES
RAW_INFERENCE_COLUMNS = [c for c in REQUIRED_COLUMNS if c != "meter_reading"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def feature_dictionary() -> list[dict]:
    """Machine-readable definitions; observed ranges are added after validation."""
    defs = [
        ("hour", "timestamp", "timestamp hour", "int8", "0..23", "daily cycle"),
        ("day_of_week", "timestamp", "Monday=0 through Sunday=6", "int8", "0..6", "weekly cycle"),
        ("day_of_month", "timestamp", "calendar day", "int8", "1..31", "within-month timing"),
        ("day_of_year", "timestamp", "calendar ordinal day", "int16", "1..366", "annual progression"),
        ("week_of_year", "timestamp", "ISO week number", "int8", "1..53", "annual weekly cycle"),
        ("month", "timestamp", "calendar month", "int8", "1..12", "seasonality"),
        ("quarter", "timestamp", "calendar quarter", "int8", "1..4", "coarse seasonality"),
        ("is_weekend", "timestamp", "day_of_week >= 5", "bool", "False..True", "occupancy schedule proxy"),
        ("hour_sin", "timestamp", "sin(2*pi*hour/24)", "float32", "-1..1", "continuous cyclical hour"),
        ("hour_cos", "timestamp", "cos(2*pi*hour/24)", "float32", "-1..1", "continuous cyclical hour"),
        ("day_of_week_sin", "timestamp", "sin(2*pi*day_of_week/7)", "float32", "-1..1", "continuous weekly cycle"),
        ("day_of_week_cos", "timestamp", "cos(2*pi*day_of_week/7)", "float32", "-1..1", "continuous weekly cycle"),
        ("month_sin", "timestamp", "sin(2*pi*(month-1)/12)", "float32", "-1..1", "continuous annual cycle"),
        ("month_cos", "timestamp", "cos(2*pi*(month-1)/12)", "float32", "-1..1", "continuous annual cycle"),
        ("building_age_2016", "year_built", "max(0, 2016-year_built)", "int16", "0..116", "building vintage"),
        ("log_square_feet", "square_feet", "log1p(square_feet)", "float32", ">=0", "compress area scale"),
        ("square_feet_per_floor", "square_feet,floor_count", "square_feet/max(floor_count,1)", "float32", ">0", "approximate floor plate"),
        ("temperature_difference", "air_temperature,dew_temperature", "air_temperature-dew_temperature", "float32", "observed", "air moisture spread"),
        ("relative_humidity", "air_temperature,dew_temperature", "100*exp(17.625*Td/(243.04+Td)-17.625*T/(243.04+T)), clipped", "float32", "0..100", "Magnus-formula humidity approximation"),
        ("wind_direction_sin", "wind_direction", "sin(direction*pi/180)", "float32", "-1..1", "circular wind direction"),
        ("wind_direction_cos", "wind_direction", "cos(direction*pi/180)", "float32", "-1..1", "circular wind direction"),
        ("is_precipitating", "precip_depth_1_hr", "precip_depth_1_hr > 0", "bool", "False..True", "active precipitation"),
        ("is_freezing", "air_temperature", "air_temperature <= 0 C", "bool", "False..True", "freezing conditions"),
        ("is_hot", "air_temperature", "air_temperature >= 30 C", "bool", "False..True", "documented hot-weather threshold"),
        ("heating_degree_proxy", "air_temperature", "max(0,18-air_temperature)", "float32", ">=0", "heating demand; 18 C balance point"),
        ("cooling_degree_proxy", "air_temperature", "max(0,air_temperature-18)", "float32", ">=0", "cooling demand; 18 C balance point"),
        ("log_square_feet_x_air_temperature", "square_feet,air_temperature", "log1p(square_feet)*air_temperature", "float32", "observed", "size-temperature interaction"),
        ("building_age_x_air_temperature", "year_built,air_temperature", "building_age_2016*air_temperature", "float32", "observed", "vintage-temperature interaction"),
        ("heating_degree_x_log_square_feet", "air_temperature,square_feet", "heating_degree_proxy*log_square_feet", "float32", ">=0", "size-adjusted heating exposure"),
        ("cooling_degree_x_log_square_feet", "air_temperature,square_feet", "cooling_degree_proxy*log_square_feet", "float32", ">=0", "size-adjusted cooling exposure"),
    ]
    return [{"feature_name": n, "source_columns": s.split(","), "formula": f, "data_type": d,
             "expected_range": r, "modelling_purpose": p,
             "leakage_risk": "None apparent: deterministic predictor/timestamp inputs only; no target usage"}
            for n, s, f, d, r, p in defs]


def validate_input(parquet: pq.ParquetFile, preprocessing_metrics: Path | None = None) -> dict:
    names = parquet.schema_arrow.names
    missing_required = sorted(set(REQUIRED_COLUMNS) - set(names))
    if missing_required:
        raise ValueError(f"Required input columns missing: {missing_required}")
    if names != REQUIRED_COLUMNS:
        raise ValueError("Input column order/schema does not match the expected clean dataset.")
    if parquet.metadata.num_rows != EXPECTED_ROWS:
        raise ValueError(f"Expected {EXPECTED_ROWS:,} rows, found {parquet.metadata.num_rows:,}.")
    report_match = None
    if preprocessing_metrics and preprocessing_metrics.exists():
        prior = json.loads(preprocessing_metrics.read_text(encoding="utf-8"))
        report_match = prior["output"]["rows"] == parquet.metadata.num_rows and prior["output"]["columns"] == len(names)
        if not report_match:
            raise ValueError("Input schema/count conflicts with preprocessing statistics.")
    return {"required_columns_present": True, "expected_rows": True, "preprocessing_report_match": report_match}


def _add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic features in place. This function never reads the target."""
    ts = df["timestamp"].dt
    df["hour"] = ts.hour.astype("int8")
    df["day_of_week"] = ts.dayofweek.astype("int8")
    df["day_of_month"] = ts.day.astype("int8")
    df["day_of_year"] = ts.dayofyear.astype("int16")
    df["week_of_year"] = ts.isocalendar().week.astype("int8")
    df["month"] = ts.month.astype("int8")
    df["quarter"] = ts.quarter.astype("int8")
    df["is_weekend"] = df["day_of_week"].ge(5)
    df["hour_sin"] = np.sin(2*np.pi*df["hour"]/24).astype("float32")
    df["hour_cos"] = np.cos(2*np.pi*df["hour"]/24).astype("float32")
    df["day_of_week_sin"] = np.sin(2*np.pi*df["day_of_week"]/7).astype("float32")
    df["day_of_week_cos"] = np.cos(2*np.pi*df["day_of_week"]/7).astype("float32")
    df["month_sin"] = np.sin(2*np.pi*(df["month"]-1)/12).astype("float32")
    df["month_cos"] = np.cos(2*np.pi*(df["month"]-1)/12).astype("float32")

    df["building_age_2016"] = (2016-df["year_built"]).clip(lower=0).round().astype("int16")
    df["log_square_feet"] = np.log1p(df["square_feet"]).astype("float32")
    safe_floors = df["floor_count"].clip(lower=1)
    df["square_feet_per_floor"] = (df["square_feet"]/safe_floors).astype("float32")

    temp, dew = df["air_temperature"], df["dew_temperature"]
    df["temperature_difference"] = (temp-dew).astype("float32")
    rh = 100*np.exp((17.625*dew)/(243.04+dew) - (17.625*temp)/(243.04+temp))
    df["relative_humidity"] = rh.clip(0, 100).astype("float32")
    radians = np.deg2rad(df["wind_direction"])
    df["wind_direction_sin"] = np.sin(radians).astype("float32")
    df["wind_direction_cos"] = np.cos(radians).astype("float32")
    df["is_precipitating"] = df["precip_depth_1_hr"].gt(0)
    df["is_freezing"] = temp.le(0)
    df["is_hot"] = temp.ge(30)
    df["heating_degree_proxy"] = (18-temp).clip(lower=0).astype("float32")
    df["cooling_degree_proxy"] = (temp-18).clip(lower=0).astype("float32")

    df["log_square_feet_x_air_temperature"] = (df["log_square_feet"]*temp).astype("float32")
    df["building_age_x_air_temperature"] = (df["building_age_2016"]*temp).astype("float32")
    df["heating_degree_x_log_square_feet"] = (df["heating_degree_proxy"]*df["log_square_feet"]).astype("float32")
    df["cooling_degree_x_log_square_feet"] = (df["cooling_degree_proxy"]*df["log_square_feet"]).astype("float32")
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create the Task 2.3 training dataset while preserving the target."""
    return _add_engineered_features(df)[REQUIRED_COLUMNS + ENGINEERED_FEATURES]


def create_features_for_inference(df: pd.DataFrame) -> pd.DataFrame:
    """Create the exact Task 2.3 features without requiring ``meter_reading``.

    Input validation belongs to the production inference contract; this helper
    deliberately contains only the shared deterministic feature formulas.
    """
    missing = sorted(set(RAW_INFERENCE_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Raw inference columns missing: {missing}")
    return _add_engineered_features(df.copy())[RAW_INFERENCE_COLUMNS + ENGINEERED_FEATURES]


def update_ranges(ranges: dict, df: pd.DataFrame) -> None:
    for col in ENGINEERED_FEATURES:
        values = df[col]
        lo, hi = values.min(), values.max()
        if isinstance(lo, (np.bool_, bool)): lo, hi = bool(lo), bool(hi)
        else: lo, hi = float(lo), float(hi)
        ranges[col] = {"min": lo if col not in ranges else min(ranges[col]["min"], lo),
                       "max": hi if col not in ranges else max(ranges[col]["max"], hi)}


def duplicate_hash_count(parts: list[np.ndarray]) -> int:
    hashes = np.concatenate(parts); hashes.sort()
    return int(np.count_nonzero(hashes[1:] == hashes[:-1]))


def run(input_path: Path, output_path: Path, metrics_path: Path,
        report_path: Path = DEFAULT_REPORT, notebook_path: Path = DEFAULT_NOTEBOOK) -> dict:
    started = time.perf_counter()
    logging.info("Validating clean input: %s", input_path)
    input_path, output_path, metrics_path = map(Path, (input_path, output_path, metrics_path))
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Output path must not overwrite the clean input dataset.")
    input_stat = input_path.stat()
    input_hash_before = sha256(input_path)
    source = pq.ParquetFile(input_path)
    validation = validate_input(source, ROOT / "reports" / "week2_preprocessing_statistics.json")
    output_path.parent.mkdir(parents=True, exist_ok=True); metrics_path.parent.mkdir(parents=True, exist_ok=True)

    writer = None; ranges = {}; key_hashes = []; input_bytes = output_bytes = 0
    missing_input = invalid_timestamps = 0
    try:
        for i in range(source.metadata.num_row_groups):
            logging.info("Processing row group %d/%d", i+1, source.metadata.num_row_groups)
            table = source.read_row_group(i); input_bytes += table.nbytes
            chunk = table.to_pandas()
            missing_input += int(chunk.isna().sum().sum())
            invalid_timestamps += int(chunk["timestamp"].isna().sum())
            key_hashes.append(pd.util.hash_pandas_object(chunk[KEY_COLUMNS], index=False).to_numpy())
            featured = create_features(chunk)
            if featured.isna().any(axis=None): raise ValueError(f"Missing values produced in row group {i}.")
            numeric = featured.select_dtypes(include=["number"])
            if np.isinf(numeric.to_numpy()).any(): raise ValueError(f"Infinite values produced in row group {i}.")
            update_ranges(ranges, featured)
            out_table = pa.Table.from_pandas(featured, preserve_index=False); output_bytes += out_table.nbytes
            if writer is None: writer = pq.ParquetWriter(output_path, out_table.schema, compression="snappy")
            writer.write_table(out_table)
    except Exception:
        if writer is not None: writer.close(); writer = None
        if output_path.exists(): output_path.unlink()
        raise
    finally:
        if writer is not None: writer.close()
    duplicate_keys = duplicate_hash_count(key_hashes)
    if missing_input or invalid_timestamps or duplicate_keys:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"Input validation failed: missing={missing_input}, invalid timestamps={invalid_timestamps}, duplicate keys={duplicate_keys}")

    logging.info("Independently reloading and validating output")
    output = pq.ParquetFile(output_path)
    if output.metadata.num_rows != EXPECTED_ROWS or output.schema_arrow.names != REQUIRED_COLUMNS + ENGINEERED_FEATURES:
        raise RuntimeError("Saved output row count or schema is invalid.")
    remaining_missing = infinite_values = 0; target_unchanged = originals_unchanged = True
    output_duplicate_hashes = []
    for i in range(output.metadata.num_row_groups):
        original = source.read_row_group(i).to_pandas()
        featured = output.read_row_group(i).to_pandas()
        try: pd.testing.assert_frame_equal(featured[REQUIRED_COLUMNS], original[REQUIRED_COLUMNS], check_dtype=True)
        except AssertionError: originals_unchanged = False
        target_unchanged &= np.array_equal(featured["meter_reading"].to_numpy(), original["meter_reading"].to_numpy(), equal_nan=True)
        remaining_missing += int(featured.isna().sum().sum())
        infinite_values += int(np.isinf(featured.select_dtypes(include=["number"]).to_numpy()).sum())
        output_duplicate_hashes.append(pd.util.hash_pandas_object(featured[KEY_COLUMNS], index=False).to_numpy())
    output_duplicate_keys = duplicate_hash_count(output_duplicate_hashes)
    input_hash_after = sha256(input_path)
    input_unchanged = input_hash_before == input_hash_after and input_stat.st_size == input_path.stat().st_size and input_stat.st_mtime_ns == input_path.stat().st_mtime_ns
    definitions = feature_dictionary()
    for item in definitions: item["observed_range"] = ranges[item["feature_name"]]
    leakage_safe = all("meter_reading" not in item["source_columns"] for item in definitions)
    passed = all([target_unchanged, originals_unchanged, input_unchanged, leakage_safe,
                  remaining_missing == 0, infinite_values == 0, duplicate_keys == 0,
                  output_duplicate_keys == 0, output.metadata.num_rows == source.metadata.num_rows])
    if not passed: raise RuntimeError("Independent final feature validation failed.")

    metrics = {
        "input": {"path": str(input_path.relative_to(ROOT)).replace("\\", "/"), "rows": source.metadata.num_rows,
                  "columns": len(source.schema_arrow.names), "file_size_mb": round(input_path.stat().st_size/2**20, 2),
                  "logical_memory_mb": round(input_bytes/2**20, 2), "sha256": input_hash_before},
        "output": {"path": str(output_path.relative_to(ROOT)).replace("\\", "/"), "rows": output.metadata.num_rows,
                   "columns": len(output.schema_arrow.names), "file_size_mb": round(output_path.stat().st_size/2**20, 2),
                   "logical_memory_mb": round(output_bytes/2**20, 2), "row_groups": output.metadata.num_row_groups},
        "added_column_count": len(ENGINEERED_FEATURES), "engineered_features": ENGINEERED_FEATURES,
        "feature_dictionary": definitions, "categorical_handling": {
            "categorical_model_inputs": ["primary_use", "meter", "site_id", "building_id"],
            "numeric_identifiers": ["building_id", "site_id", "meter"],
            "grouping_or_splitting_identifiers": ["building_id", "meter", "site_id", "timestamp"],
            "linear_model_note": "Do not treat integer IDs as continuous; encode after time splitting using training data only.",
        },
        "lag_rolling_decision": "Deferred: the prediction horizon and inference-time availability of prior meter readings are not yet established. Any future implementation must sort chronologically, group by building_id and meter, shift before rolling, handle initial rows explicitly, and fit only within time-safe partitions.",
        "validation": {**validation, "input_missing_values": missing_input, "invalid_timestamps": invalid_timestamps,
                       "input_duplicate_keys": duplicate_keys, "output_duplicate_keys": output_duplicate_keys,
                       "remaining_missing_values": remaining_missing, "infinite_values": infinite_values,
                       "target_unchanged": target_unchanged, "original_columns_unchanged": originals_unchanged,
                       "input_file_unchanged": input_unchanged, "no_target_derived_features": leakage_safe,
                       "ranges": ranges, "passed": passed},
        "processing_duration_seconds": round(time.perf_counter()-started, 2),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_report(metrics, report_path); write_notebook(notebook_path)
    return metrics


def write_report(m: dict, path: Path) -> None:
    defs = m["feature_dictionary"]
    feature_rows = "\n".join(f"| `{x['feature_name']}` | {', '.join(f'`{s}`' for s in x['source_columns'])} | {x['formula']} | `{x['data_type']}` | {x['expected_range']} | {x['modelling_purpose']} |" for x in defs)
    ranges = m["validation"]["ranges"]
    range_rows = "\n".join(f"| `{name}` | {value['min']:.6g} | {value['max']:.6g} |" for name, value in ranges.items())
    report = f"""# Week 2 Task 2.3 — Feature Engineering Report

## Objective and Input Summary

Create deterministic, model-ready predictors from `{m['input']['path']}` while retaining target, timestamp, identifiers and every original predictor. Input: **{m['input']['rows']:,} rows × {m['input']['columns']} columns**; output: **{m['output']['rows']:,} rows × {m['output']['columns']} columns**.

## Feature-Engineering Principles

Features use only timestamps and observed predictor columns. No target aggregate, target encoding, lag, rolling statistic, fitted encoder, scaling, split, outlier removal or model was created. Processing was chunked by Parquet row group, deterministic, and preserved row order. Cyclical sine/cosine pairs place adjacent clock/calendar endpoints near each other geometrically.

## Column Roles

| Role | Columns |
| --- | --- |
| Original predictors | `square_feet`, `year_built`, `floor_count`, `air_temperature`, `cloud_coverage`, `dew_temperature`, `precip_depth_1_hr`, `sea_level_pressure`, `wind_direction`, `wind_speed` |
| Engineered predictors | {', '.join(f'`{x}`' for x in ENGINEERED_FEATURES)} |
| Identifiers | `building_id`, `site_id` |
| Categorical variables | `primary_use`, `meter`, `site_id`, `building_id` |
| Timestamp | `timestamp` (retained for chronological splitting) |
| Target | `meter_reading` (retained and byte-for-byte value validated) |

## Complete Feature Dictionary

| Feature | Source columns | Formula | Type | Expected range | Purpose |
| --- | --- | --- | --- | --- | --- |
{feature_rows}

Relative humidity uses the Magnus approximation with constants 17.625 and 243.04 °C and is clipped to its physical 0–100% range. Heating/cooling degree proxies use a documented **18 °C balance point**. `is_hot` uses **30 °C**; `is_freezing` uses **0 °C**; precipitation means measured depth greater than zero. Building age uses the dataset year 2016 and is clipped at zero.

## Categorical Handling Decision

`primary_use`, `meter`, `site_id`, and `building_id` are retained unchanged. They should be declared categorical for category-aware tree models. Integer identifiers must not be interpreted as continuous by linear/distance-based models; encoding must occur only after time splitting and be fit on training data. `building_id`, `meter`, `site_id`, and `timestamp` remain available for grouping, auditing and splitting. High-cardinality identifiers were not dropped.

## Lag and Rolling Feature Decision

**Deferred.** The application’s prediction horizon (next hour versus arbitrary future time) and availability of historical readings at inference are not established. Implementing them now could leak current/future targets. A future experiment must group by (`building_id`, `meter`), sort chronologically, apply `shift` before every rolling calculation, define first-observation behavior, construct features separately within time-safe partitions, prove inference availability, and measure memory cost.

## Leakage Prevention and Target Preservation

The machine-readable dictionary confirms that no engineered feature lists `meter_reading` as a source. Independent row-group comparison verified the target and all 16 original columns unchanged. The clean input SHA-256 remained `{m['input']['sha256']}` before and after the run.

## Feature Validation

- Row count unchanged: **{m['validation']['passed']}** ({m['output']['rows']:,})
- Duplicate logical keys before/after: **{m['validation']['input_duplicate_keys']:,} / {m['validation']['output_duplicate_keys']:,}**
- Missing values / infinite values: **{m['validation']['remaining_missing_values']:,} / {m['validation']['infinite_values']:,}**
- Invalid timestamps: **{m['validation']['invalid_timestamps']:,}**
- Original columns and target unchanged: **{m['validation']['original_columns_unchanged']} / {m['validation']['target_unchanged']}**
- Input file unchanged: **{m['validation']['input_file_unchanged']}**
- Overall validation: **PASSED**

### Observed Engineered-Feature Ranges

| Feature | Minimum | Maximum |
| --- | ---: | ---: |
{range_rows}

## Memory and Storage Impact

| Measure | Input | Output |
| --- | ---: | ---: |
| Logical Arrow memory | {m['input']['logical_memory_mb']:.2f} MB | {m['output']['logical_memory_mb']:.2f} MB |
| Snappy Parquet size | {m['input']['file_size_mb']:.2f} MB | {m['output']['file_size_mb']:.2f} MB |
| Columns | {m['input']['columns']} | {m['output']['columns']} |

Added columns: **{m['added_column_count']}**. Processing duration: **{m['processing_duration_seconds']:.2f} seconds**. Bounded calendar values use `int8`/`int16`, indicators use Boolean, and engineered continuous values use `float32`.

## Remaining Modelling Risks and Baseline Recommendation

IDs require model-appropriate encoding after chronological splitting; imputed metadata/weather uncertainty remains; interaction magnitudes and collinearity may affect linear models; site/building generalization must be evaluated; and target skew/outliers remain intentionally untouched. For baselines, start with calendar/cyclical variables, original weather, degree proxies, log area, building age, floor-adjusted area, meter and primary use using training-only categorical handling. Interaction features can be ablated.

## Readiness for Task 2.4

The feature dataset is validated and ready for a separate time-based splitting task. Task 2.3 stops here; no split, encoding fit, scaling or model training has occurred.
"""
    path.write_text(report, encoding="utf-8")


def write_notebook(path: Path) -> None:
    def md(s): return {"cell_type":"markdown","metadata":{},"source":[x+"\n" for x in s.strip().splitlines()]}
    def code(s): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[x+"\n" for x in s.strip().splitlines()]}
    cells = [
        md("# Week 2 — Task 2.3: Feature Engineering\n\nDeterministic, memory-conscious predictor construction only. No split, fitted encoding, scaling, target-derived features or modelling."),
        md("## 1. Input validation"),
        code("from pathlib import Path\nimport json, sys\nimport pyarrow.parquet as pq\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nsys.path.insert(0, str(ROOT))\nfrom scripts.week2_feature_engineering import (DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_METRICS, validate_input, create_features, feature_dictionary)\nsource = pq.ParquetFile(DEFAULT_INPUT)\nvalidate_input(source, ROOT/'reports'/'week2_preprocessing_statistics.json')"),
        md("## 2. Feature-engineering goals\n\nRetain all original data while adding compact calendar, building, weather and interaction predictors that are available without reading the target."),
        md("## 3. Time features\n\nCalendar integers retain timestamp semantics. Sine/cosine pairs represent hour, weekday and month cycles without false endpoint distance."),
        md("## 4. Building features\n\nAge is anchored to 2016 and clipped at zero; log area compresses scale; area per floor uses a denominator bounded below by one."),
        md("## 5. Weather features\n\nFeatures include temperature/dew spread, Magnus relative humidity, circular wind direction, documented indicators, and 18 °C degree proxies."),
        md("## 6. Interaction features\n\nFour bounded-order multiplicative terms connect building scale/vintage with temperature or degree demand. None uses target statistics."),
        code("sample = source.read_row_group(0).slice(0, 10_000).to_pandas()\npreview = create_features(sample)\npreview.head()"),
        md("## 7. Lag-feature decision\n\nDeferred because prediction horizon and inference-time target history are unknown. Future lags require chronological (`building_id`, `meter`) grouping and a shift before rolling."),
        md("## 8. Run and feature validation\n\nRun the CLI from the project root to reproduce the full artifact: `python scripts/week2_feature_engineering.py`. The script independently reloads all row groups and validates keys, values, ranges, target preservation and input fingerprint."),
        code("metrics = json.loads(DEFAULT_METRICS.read_text(encoding='utf-8'))\nmetrics['validation']"),
        md("## 9. Memory impact"),
        code("{k: metrics[k] for k in ['input','output','added_column_count','processing_duration_seconds']}"),
        md("## 10. Final feature inventory"),
        code("import pandas as pd\npd.DataFrame(metrics['feature_dictionary'])"),
        md("## 11. Readiness for model splitting\n\nThe timestamp and grouping identifiers are retained. The dataset is ready for a separate chronological splitting task; no split or model preparation is performed here."),
    ]
    nb={"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3"}},"nbformat":4,"nbformat_minor":5}
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(nb, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--notebook", type=Path, default=DEFAULT_NOTEBOOK)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(args.input, args.output, args.metrics, args.report, args.notebook)
    print(json.dumps({"rows":result["output"]["rows"],"columns":result["output"]["columns"],
                      "features_added":result["added_column_count"],"validation":result["validation"]["passed"]}, indent=2))


if __name__ == "__main__": main()
