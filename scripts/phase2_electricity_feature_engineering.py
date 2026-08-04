"""Phase 2 electricity-only, leakage-safe feature engineering.

The pipeline is CSV-native, chunked, and leaves the v1 feature pipeline intact.
It externally partitions rows by site/month, sorts each bounded partition, and
uses causal forward weather carry. Site/global fallback medians are fitted only
on the configured training period (default: through 2016-08-31 23:59:59).
No feature reads or derives from ``meter_reading``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "electricity_processed.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "electricity_features.csv"
DEFAULT_REPORT_DIR = ROOT / "reports"
DEFAULT_TRAINING_END = pd.Timestamp("2016-08-31 23:59:59")

TARGET = "meter_reading"
TIMESTAMP = "timestamp"
IDENTIFIERS = ["building_id", "site_id"]
CATEGORICAL = ["primary_use", "season"]
RAW_WEATHER = [
    "air_temperature", "cloud_coverage", "dew_temperature",
    "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
]
RAW_COLUMNS = [
    "building_id", "meter", "timestamp", "meter_reading", "site_id",
    "primary_use", "square_feet", "year_built", "floor_count", *RAW_WEATHER,
]
CALENDAR = [
    "year", "quarter", "month", "week_of_year", "day", "day_of_year",
    "weekday", "hour", "is_weekend", "season",
]
CYCLICAL = [
    "hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "month_sin", "month_cos",
]
BUILDING = ["building_age", "log_square_feet", "area_per_floor"]
WEATHER_DERIVED = [
    "temperature_difference", "relative_humidity_proxy", "wind_x", "wind_y",
    "temperature_x_square_feet", "hour_x_temperature", "cooling_demand_proxy",
    "heating_demand_proxy",
]
MISSING_INDICATORS = [f"{column}_missing" for column in RAW_WEATHER]
RETAINED_RAW = [
    "building_id", "site_id", "primary_use", "square_feet", "year_built",
    "floor_count", "timestamp", *RAW_WEATHER, TARGET,
]
OUTPUT_COLUMNS = RETAINED_RAW + MISSING_INDICATORS + CALENDAR + CYCLICAL + BUILDING + WEATHER_DERIVED
NON_PREDICTORS = [TARGET, TIMESTAMP, *IDENTIFIERS]
NUMERIC_PREDICTORS = [
    "square_feet", "year_built", "floor_count", *RAW_WEATHER,
    *MISSING_INDICATORS, *[c for c in CALENDAR if c != "season"],
    *CYCLICAL, *BUILDING, *WEATHER_DERIVED,
]

FORMULAS = {
    "year": "timestamp calendar year",
    "quarter": "timestamp calendar quarter (1..4)",
    "month": "timestamp calendar month (1..12)",
    "week_of_year": "ISO-8601 week number",
    "day": "timestamp day of month",
    "day_of_year": "timestamp ordinal day of year",
    "weekday": "Monday=0 through Sunday=6",
    "hour": "timestamp hour (0..23)",
    "is_weekend": "1 when weekday >= 5, otherwise 0",
    "season": "winter=Dec-Feb, spring=Mar-May, summer=Jun-Aug, autumn=Sep-Nov",
    "hour_sin": "sin(2*pi*hour/24)",
    "hour_cos": "cos(2*pi*hour/24)",
    "weekday_sin": "sin(2*pi*weekday/7)",
    "weekday_cos": "cos(2*pi*weekday/7)",
    "month_sin": "sin(2*pi*(month-1)/12)",
    "month_cos": "cos(2*pi*(month-1)/12)",
    "building_age": "max(0, timestamp year - year_built); missing when year_built is invalid/missing",
    "log_square_feet": "log1p(square_feet) only when square_feet > 0; otherwise missing",
    "area_per_floor": "square_feet/floor_count only when square_feet > 0 and floor_count > 0; otherwise missing",
    "temperature_difference": "air_temperature - dew_temperature",
    "relative_humidity_proxy": "100*exp(17.625*Td/(243.04+Td) - 17.625*T/(243.04+T)), clipped to 0..100; approximation only",
    "wind_x": "wind_speed*cos(wind_direction*pi/180)",
    "wind_y": "wind_speed*sin(wind_direction*pi/180)",
    "temperature_x_square_feet": "air_temperature*square_feet when square_feet is valid",
    "hour_x_temperature": "hour*air_temperature",
    "cooling_demand_proxy": "max(0, air_temperature-18); heuristic 18 C balance point",
    "heating_demand_proxy": "max(0, 18-air_temperature); heuristic 18 C balance point",
    **{f"{column}_missing": f"1 when source {column} was missing before deterministic weather treatment" for column in RAW_WEATHER},
}


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)):
        return None if not math.isfinite(float(value)) else float(value)
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_source_chunk(chunk: pd.DataFrame) -> None:
    missing = sorted(set(RAW_COLUMNS) - set(chunk.columns))
    if missing:
        raise ValueError(f"Required source columns missing: {missing}")
    if chunk["meter"].isna().any() or not chunk["meter"].eq(0).all():
        values = sorted(chunk.loc[chunk["meter"].ne(0) | chunk["meter"].isna(), "meter"].drop_duplicates().astype(str).tolist())
        raise ValueError(f"Non-electricity meter values found; expected meter == 0 only, found: {values[:10]}")
    if chunk[TARGET].isna().any() or chunk[TARGET].lt(0).any():
        raise ValueError("Target must be present and nonnegative; zero values are valid and preserved.")
    if chunk[TIMESTAMP].isna().any():
        raise ValueError("Invalid or missing timestamps found.")


def season_for_month(month: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
            ["winter", "spring", "summer"], default="autumn",
        ), index=month.index, dtype="string",
    )


def create_features(chunk: pd.DataFrame) -> pd.DataFrame:
    """Create deterministic features without reading target values."""
    required_predictors = sorted(set(RAW_COLUMNS) - {TARGET, "meter"})
    missing = sorted(set(required_predictors) - set(chunk.columns))
    if missing:
        raise ValueError(f"Predictor source columns missing: {missing}")
    result = chunk.copy()
    if not isinstance(result[TIMESTAMP].dtype, pd.DatetimeTZDtype) and not pd.api.types.is_datetime64_any_dtype(result[TIMESTAMP]):
        result[TIMESTAMP] = pd.to_datetime(result[TIMESTAMP], errors="raise", format="mixed")
    for column in RAW_WEATHER:
        indicator = f"{column}_missing"
        if indicator not in result.columns:
            result[indicator] = result[column].isna().astype("int8")
    ts = result[TIMESTAMP].dt
    result["year"] = ts.year.astype("int16")
    result["quarter"] = ts.quarter.astype("int8")
    result["month"] = ts.month.astype("int8")
    result["week_of_year"] = ts.isocalendar().week.astype("int8")
    result["day"] = ts.day.astype("int8")
    result["day_of_year"] = ts.dayofyear.astype("int16")
    result["weekday"] = ts.dayofweek.astype("int8")
    result["hour"] = ts.hour.astype("int8")
    result["is_weekend"] = result["weekday"].ge(5).astype("int8")
    result["season"] = season_for_month(result["month"])
    result["hour_sin"] = np.sin(2*np.pi*result["hour"]/24).astype("float32")
    result["hour_cos"] = np.cos(2*np.pi*result["hour"]/24).astype("float32")
    result["weekday_sin"] = np.sin(2*np.pi*result["weekday"]/7).astype("float32")
    result["weekday_cos"] = np.cos(2*np.pi*result["weekday"]/7).astype("float32")
    result["month_sin"] = np.sin(2*np.pi*(result["month"]-1)/12).astype("float32")
    result["month_cos"] = np.cos(2*np.pi*(result["month"]-1)/12).astype("float32")

    valid_year = result["year_built"].between(1800, result["year"])
    result["building_age"] = (result["year"]-result["year_built"]).where(valid_year).clip(lower=0).astype("float32")
    valid_area = result["square_feet"].gt(0) & result["square_feet"].notna()
    valid_floor = result["floor_count"].gt(0) & result["floor_count"].notna()
    result["log_square_feet"] = np.log1p(result["square_feet"].where(valid_area)).astype("float32")
    result["area_per_floor"] = (result["square_feet"].where(valid_area)/result["floor_count"].where(valid_floor)).astype("float32")

    temp, dew = result["air_temperature"], result["dew_temperature"]
    result["temperature_difference"] = (temp-dew).astype("float32")
    humidity = 100*np.exp((17.625*dew)/(243.04+dew) - (17.625*temp)/(243.04+temp))
    result["relative_humidity_proxy"] = humidity.clip(0, 100).astype("float32")
    radians = np.deg2rad(result["wind_direction"])
    result["wind_x"] = (result["wind_speed"]*np.cos(radians)).astype("float32")
    result["wind_y"] = (result["wind_speed"]*np.sin(radians)).astype("float32")
    result["temperature_x_square_feet"] = (temp*result["square_feet"].where(valid_area)).astype("float32")
    result["hour_x_temperature"] = (result["hour"]*temp).astype("float32")
    result["cooling_demand_proxy"] = (temp-18).clip(lower=0).astype("float32")
    result["heating_demand_proxy"] = (18-temp).clip(lower=0).astype("float32")
    return result[OUTPUT_COLUMNS]


def fit_training_weather_medians(records: dict[tuple[int, pd.Timestamp], tuple]) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    if not records:
        raise ValueError("No training-period weather records were found for fallback fitting.")
    weather = pd.DataFrame.from_records(
        [(site, timestamp, *values) for (site, timestamp), values in records.items()],
        columns=["site_id", "timestamp", *RAW_WEATHER],
    )
    site_frame = weather.groupby("site_id", observed=True)[RAW_WEATHER].median()
    global_series = weather[RAW_WEATHER].median()
    global_medians = {column: float(global_series[column]) for column in RAW_WEATHER}
    site_medians = {
        int(site): {
            column: float(row[column]) if pd.notna(row[column]) else global_medians[column]
            for column in RAW_WEATHER
        }
        for site, row in site_frame.iterrows()
    }
    return site_medians, global_medians


def treat_weather_forward_only(
    frame: pd.DataFrame,
    last_seen: dict[int, dict[str, float]],
    site_medians: dict[int, dict[str, float]],
    global_medians: dict[str, float],
) -> pd.DataFrame:
    """Causal weather fill: source-missing indicator, prior value, frozen medians."""
    result = frame.copy()
    for column in RAW_WEATHER:
        result[f"{column}_missing"] = result[column].isna().astype("int8")
    for site, indexes in result.groupby("site_id", sort=False).groups.items():
        site = int(site)
        ordered = result.loc[indexes, RAW_WEATHER]
        previous = last_seen.setdefault(site, {})
        for column in RAW_WEATHER:
            series = ordered[column]
            if column in previous:
                series = series.copy()
                if pd.isna(series.iloc[0]):
                    series.iloc[0] = previous[column]
            series = series.ffill()
            fallback = site_medians.get(site, {}).get(column, global_medians[column])
            series = series.fillna(fallback).fillna(global_medians[column])
            result.loc[indexes, column] = series.to_numpy()
            observed = series.dropna()
            if not observed.empty:
                previous[column] = float(observed.iloc[-1])
    return result


def schema_payload(dtypes: dict[str, str], generated_at: str) -> dict[str, Any]:
    target_sources = {name: formula for name, formula in FORMULAS.items() if TARGET in formula}
    return {
        "schema_version": "2.0.0-electricity",
        "target_column": TARGET,
        "identifier_columns": IDENTIFIERS,
        "numeric_feature_columns": NUMERIC_PREDICTORS,
        "categorical_feature_columns": CATEGORICAL,
        "timestamp_column": TIMESTAMP,
        "excluded_columns": ["meter"],
        "feature_count": len(NUMERIC_PREDICTORS) + len(CATEGORICAL),
        "formulas": FORMULAS,
        "expected_dtypes": dtypes,
        "missing_value_strategy": {
            "ordering": "Externally partition by site/month; sort by site_id, timestamp, building_id within each partition",
            "weather": "Source missingness indicators, causal forward carry within site, then site training-period median, then global training-period median",
            "training_period_end_inclusive": DEFAULT_TRAINING_END.isoformat(),
            "building_metadata": "Raw missing values retained; safe derived features remain missing when inputs are invalid. Model-time preprocessing must be fitted on training data only.",
            "leakage_boundary": "No bidirectional interpolation. Validation/test weather never fills from future rows. Fallback statistics use training-period timestamps only.",
        },
        "meter_removed_from_predictors": "meter" not in NUMERIC_PREDICTORS + CATEGORICAL,
        "target_derived_features": bool(target_sources),
        "target_derived_feature_details": target_sources,
        "generation_timestamp": generated_at,
    }


def feature_dictionary_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_meanings = {
        "building_id": ("identifier", "source building_id", "Building identifier", "observed IDs", "not imputed", False),
        "site_id": ("identifier", "source site_id", "Site identifier", "0..15 observed", "not imputed", False),
        "primary_use": ("categorical", "source primary_use", "Building use category", "observed categories", "model-time handling", True),
        "square_feet": ("building", "source square_feet", "Building floor area", ">0 when valid", "raw missing retained", True),
        "year_built": ("building", "source year_built", "Construction year", "1800..timestamp year when valid", "raw missing retained", True),
        "floor_count": ("building", "source floor_count", "Number of floors", ">0 when valid", "raw missing retained", True),
        "timestamp": ("timestamp", "source timestamp", "Observation timestamp", "2016 observed", "must be present", False),
        TARGET: ("target", f"source {TARGET}", "Electricity meter reading; unit unverified", ">=0", "must be present; zero retained", False),
    }
    for column in RAW_WEATHER:
        raw_meanings[column] = ("weather", f"source {column}", column.replace("_", " ").title(), "source-dependent", "indicator + causal carry + frozen training medians", True)
    for name in RETAINED_RAW:
        category, source, meaning, expected, missing, sent = raw_meanings[name]
        rows.append({"feature_name": name, "category": category, "source_or_formula": source, "meaning": meaning, "expected_range": expected, "missing_handling": missing, "sent_to_model": sent, "leakage_notes": "Target only; never predictor" if name == TARGET else "Raw predictor/identifier; no target derivation"})
    for name in MISSING_INDICATORS + CALENDAR + CYCLICAL + BUILDING + WEATHER_DERIVED:
        category = "missing_indicator" if name in MISSING_INDICATORS else "calendar" if name in CALENDAR else "cyclical" if name in CYCLICAL else "building" if name in BUILDING else "weather_derived"
        expected = "0..1" if name in MISSING_INDICATORS or name == "is_weekend" else "documented by formula/source"
        missing = "never missing" if name in MISSING_INDICATORS + CALENDAR + CYCLICAL else "missing if invalid building input" if name in BUILDING else "weather inputs deterministically treated first"
        rows.append({"feature_name": name, "category": category, "source_or_formula": FORMULAS[name], "meaning": name.replace("_", " ").title(), "expected_range": expected, "missing_handling": missing, "sent_to_model": True, "leakage_notes": "Deterministic predictors only; meter_reading is never read"})
    return rows


def write_dictionary(path: Path) -> None:
    lines = [
        "# Phase 2 Electricity Feature Dictionary", "",
        "The electricity unit is not verified; the target is therefore described only as an electricity meter reading or electricity consumption value.", "",
        "| Feature | Category | Source or formula | Meaning | Expected range | Missing handling | Sent to model | Leakage notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in feature_dictionary_rows():
        values = [str(row[key]).replace("|", "\\|") for key in ("feature_name", "category", "source_or_formula", "meaning", "expected_range", "missing_handling", "sent_to_model", "leakage_notes")]
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pipeline(
    input_path: Path,
    output_path: Path,
    report_dir: Path,
    chunk_size: int = 250_000,
    sample_rows: int | None = None,
    overwrite: bool = False,
    training_end: pd.Timestamp = DEFAULT_TRAINING_END,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_path, output_path, report_dir = Path(input_path), Path(output_path), Path(report_dir)
    if not input_path.is_file(): raise FileNotFoundError(input_path)
    if input_path.resolve() == output_path.resolve(): raise ValueError("Output cannot overwrite the input dataset.")
    if output_path.exists() and not overwrite: raise FileExistsError(f"Output exists: {output_path}. Use --overwrite to replace it safely.")
    if chunk_size <= 0: raise ValueError("Chunk size must be positive.")
    output_path.parent.mkdir(parents=True, exist_ok=True); report_dir.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(output_path.suffix + ".tmp")
    work_dir = output_path.parent / f".{output_path.stem}.work"
    if temp_output.exists(): temp_output.unlink()
    if work_dir.exists():
        if not overwrite: raise FileExistsError(f"Prior work directory exists: {work_dir}. Use --overwrite to clean it.")
        resolved = work_dir.resolve()
        if resolved.parent != output_path.parent.resolve(): raise RuntimeError("Unsafe work-directory cleanup target.")
        shutil.rmtree(resolved)
    work_dir.mkdir()

    input_rows = zero_targets = invalid_area = invalid_year = invalid_floor = 0
    missing_before = {column: 0 for column in RAW_WEATHER}
    weather_training_records: dict[tuple[int, pd.Timestamp], tuple] = {}
    partition_paths: dict[tuple[int, str], Path] = {}
    original_hashes: list[np.ndarray] = []
    try:
        remaining = sample_rows
        reader = pd.read_csv(input_path, chunksize=chunk_size, parse_dates=[TIMESTAMP])
        for chunk in reader:
            if remaining is not None:
                if remaining <= 0: break
                chunk = chunk.iloc[:remaining].copy(); remaining -= len(chunk)
            validate_source_chunk(chunk)
            input_rows += len(chunk); zero_targets += int(chunk[TARGET].eq(0).sum())
            invalid_area += int(chunk["square_feet"].isna().sum() + chunk["square_feet"].le(0).sum())
            years = chunk[TIMESTAMP].dt.year
            invalid_year += int((chunk["year_built"].isna() | ~chunk["year_built"].between(1800, years)).sum())
            invalid_floor += int((chunk["floor_count"].isna() | chunk["floor_count"].le(0)).sum())
            for column in RAW_WEATHER: missing_before[column] += int(chunk[column].isna().sum())
            original_hashes.append(pd.util.hash_pandas_object(chunk[["building_id", TIMESTAMP, TARGET]], index=False).to_numpy())

            training = chunk.loc[chunk[TIMESTAMP].le(training_end), ["site_id", TIMESTAMP, *RAW_WEATHER]].drop_duplicates(["site_id", TIMESTAMP])
            for row in training.itertuples(index=False, name=None):
                key = (int(row[0]), pd.Timestamp(row[1]))
                values = tuple(row[2:])
                prior = weather_training_records.get(key)
                if prior is not None:
                    for left, right in zip(prior, values):
                        if pd.notna(left) and pd.notna(right) and not np.isclose(left, right):
                            raise ValueError(f"Conflicting weather values for site/timestamp {key}")
                else: weather_training_records[key] = values

            chunk["_partition_month"] = chunk[TIMESTAMP].dt.strftime("%Y%m")
            for (site, month), part in chunk.groupby(["site_id", "_partition_month"], sort=False):
                key = (int(site), str(month)); path = work_dir / f"site_{int(site):02d}_{month}.csv"
                part.drop(columns="_partition_month").to_csv(path, mode="a", header=not path.exists(), index=False)
                partition_paths[key] = path
        if input_rows == 0: raise ValueError("Input produced zero rows.")

        site_medians, global_medians = fit_training_weather_medians(weather_training_records)
        last_seen: dict[int, dict[str, float]] = {}
        output_rows = unresolved_weather_rows = infinite_count = 0
        missing_after: dict[str, int] = {}
        numeric_ranges: dict[str, dict[str, float]] = {}
        category_values = {column: set() for column in CATEGORICAL}
        output_hashes: list[np.ndarray] = []
        output_dtypes: dict[str, str] | None = None
        first_write = True
        for key in sorted(partition_paths):
            part = pd.read_csv(partition_paths[key], parse_dates=[TIMESTAMP])
            part.sort_values(["site_id", TIMESTAMP, "building_id"], kind="stable", inplace=True)
            treated = treat_weather_forward_only(part, last_seen, site_medians, global_medians)
            unresolved_weather_rows += int(treated[RAW_WEATHER].isna().any(axis=1).sum())
            featured = create_features(treated)
            if "meter" in featured.columns: raise RuntimeError("Meter leaked into final output schema.")
            if featured.columns.tolist() != OUTPUT_COLUMNS: raise RuntimeError("Nondeterministic output column order.")
            if output_dtypes is None: output_dtypes = {column: str(dtype) for column, dtype in featured.dtypes.items()}
            for column, count in featured.isna().sum().items(): missing_after[column] = missing_after.get(column, 0) + int(count)
            numeric = featured.select_dtypes(include=[np.number])
            infinite_count += int(np.isinf(numeric.to_numpy()).sum())
            for column in numeric.columns:
                values = numeric[column].dropna()
                if values.empty: continue
                low, high = float(values.min()), float(values.max())
                current = numeric_ranges.setdefault(column, {"minimum": low, "maximum": high})
                current["minimum"] = min(current["minimum"], low); current["maximum"] = max(current["maximum"], high)
            for column in CATEGORICAL: category_values[column].update(featured[column].dropna().astype(str).unique())
            output_hashes.append(pd.util.hash_pandas_object(featured, index=False).to_numpy())
            featured.to_csv(temp_output, mode="a", header=first_write, index=False)
            first_write = False; output_rows += len(featured)

        def duplicates(parts: list[np.ndarray]) -> int:
            values = np.concatenate(parts); values.sort()
            return int(np.count_nonzero(values[1:] == values[:-1]))

        original_keys = np.concatenate(original_hashes); output_full_duplicates = duplicates(output_hashes)
        if output_rows != input_rows: raise RuntimeError("Feature engineering changed row count.")
        # Re-read target/key only to prove target preservation despite site/time reordering.
        output_key_target = []
        for chunk in pd.read_csv(temp_output, chunksize=chunk_size, usecols=["building_id", TIMESTAMP, TARGET], parse_dates=[TIMESTAMP]):
            output_key_target.append(pd.util.hash_pandas_object(chunk[["building_id", TIMESTAMP, TARGET]], index=False).to_numpy())
        output_keys = np.concatenate(output_key_target)
        if not np.array_equal(np.sort(original_keys), np.sort(output_keys)): raise RuntimeError("Target/key values changed during feature generation.")
        if infinite_count: raise RuntimeError(f"Generated {infinite_count} infinite values.")
        if unresolved_weather_rows: raise RuntimeError(f"Weather treatment left {unresolved_weather_rows} unresolved rows.")
        if output_path.exists(): output_path.unlink()
        os.replace(temp_output, output_path)

        generated_at = datetime.now(timezone.utc).isoformat()
        schema = schema_payload(output_dtypes or {}, generated_at)
        if schema["target_derived_features"]: raise RuntimeError("Automated leakage check found a target-derived feature.")
        schema_path = report_dir / "phase2_electricity_feature_schema.json"
        dictionary_path = report_dir / "phase2_electricity_feature_dictionary.md"
        audit_json = report_dir / "phase2_electricity_feature_audit.json"
        audit_md = report_dir / "phase2_electricity_feature_audit.md"
        schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        write_dictionary(dictionary_path)
        audit = {
            "input_path": str(input_path), "output_path": str(output_path),
            "input_rows": input_rows, "output_rows": output_rows,
            "feature_count": schema["feature_count"], "numeric_feature_count": len(NUMERIC_PREDICTORS),
            "categorical_feature_count": len(CATEGORICAL),
            "missing_values_before_weather_treatment": missing_before,
            "missing_values_after_deterministic_treatment": missing_after,
            "rows_with_unresolved_weather_values": unresolved_weather_rows,
            "invalid_square_foot_rows": invalid_area, "invalid_year_built_rows": invalid_year,
            "invalid_floor_count_rows": invalid_floor,
            "meter_validation": {"all_rows_meter_zero": True, "meter_removed_from_predictors": schema["meter_removed_from_predictors"]},
            "duplicate_full_rows": output_full_duplicates,
            "infinite_value_count": infinite_count,
            "nan_count_by_feature": {column: missing_after.get(column, 0) for column in OUTPUT_COLUMNS},
            "numeric_minimum_maximum": numeric_ranges,
            "categorical_cardinalities": {column: len(values) for column, values in category_values.items()},
            "zero_targets_preserved": zero_targets,
            "target_derived_features": schema["target_derived_features"],
            "processing_duration_seconds": round(time.perf_counter()-started, 3),
            "output_size_bytes": output_path.stat().st_size,
            "output_sha256": sha256(output_path),
            "sample_row_limit": sample_rows,
            "training_period_end_inclusive": training_end.isoformat(),
            "model_trained": False,
        }
        audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        write_audit_markdown(audit_md, audit)
        return audit
    except Exception:
        if temp_output.exists(): temp_output.unlink()
        raise
    finally:
        if work_dir.exists():
            resolved = work_dir.resolve()
            if resolved.parent != output_path.parent.resolve(): raise RuntimeError("Unsafe work-directory cleanup target.")
            shutil.rmtree(resolved)


def write_audit_markdown(path: Path, audit: dict[str, Any]) -> None:
    before = "\n".join(f"| `{k}` | {v:,} |" for k, v in audit["missing_values_before_weather_treatment"].items())
    remaining = {k: v for k, v in audit["nan_count_by_feature"].items() if v}
    after = "\n".join(f"| `{k}` | {v:,} |" for k, v in remaining.items()) or "| None | 0 |"
    report = f"""# Phase 2 Electricity Feature Audit

## Result

The pipeline produced **{audit['output_rows']:,} rows** with **{audit['feature_count']} model features** ({audit['numeric_feature_count']} numeric and {audit['categorical_feature_count']} categorical). Meter code 0 was validated and `meter` was removed from predictors. No feature derives from the target, no model was trained, and the electricity unit remains unverified.

## Counts and integrity

| Measure | Value |
| --- | ---: |
| Input rows | {audit['input_rows']:,} |
| Output rows | {audit['output_rows']:,} |
| Zero targets preserved | {audit['zero_targets_preserved']:,} |
| Duplicate complete rows | {audit['duplicate_full_rows']:,} |
| Infinite values | {audit['infinite_value_count']:,} |
| Rows with unresolved weather | {audit['rows_with_unresolved_weather_values']:,} |
| Invalid/missing square feet rows | {audit['invalid_square_foot_rows']:,} |
| Invalid/missing year built rows | {audit['invalid_year_built_rows']:,} |
| Invalid/missing floor count rows | {audit['invalid_floor_count_rows']:,} |

## Weather missingness before treatment

| Feature | Missing rows |
| --- | ---: |
{before}

## Missing values after deterministic treatment

Weather is fully resolved. Remaining missing values are retained building metadata and safe derived building features; model-time imputation must be fitted on training data only.

| Feature | Missing rows |
| --- | ---: |
{after}

## Leakage and preprocessing policy

- Weather ordering: site/month external partitions, sorted by site, timestamp, and building.
- Weather interpolation: causal forward carry only; never bidirectional.
- Fallbacks: site median, then global median, fitted only through `{audit['training_period_end_inclusive']}`.
- Missingness indicators preserve the original weather-null state.
- Target lags, rolling targets, target means, and future-aware aggregates: absent.
- Meter removed from predictors: **{str(audit['meter_validation']['meter_removed_from_predictors']).lower()}**.
- Target-derived features: **{str(audit['target_derived_features']).lower()}**.

## Artifact

- Output: `{audit['output_path']}`
- Size: {audit['output_size_bytes'] / 2**20:,.2f} MiB
- SHA-256: `{audit['output_sha256']}`
- Processing duration: {audit['processing_duration_seconds']:.3f} seconds
"""
    path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument("--sample-rows", type=int)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--training-end", type=pd.Timestamp, default=DEFAULT_TRAINING_END)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_pipeline(args.input, args.output, args.report_dir, args.chunk_size, args.sample_rows, args.overwrite, args.training_end)
    print(json.dumps({key: result[key] for key in ("input_rows", "output_rows", "feature_count", "output_size_bytes", "output_sha256")}, indent=2))
