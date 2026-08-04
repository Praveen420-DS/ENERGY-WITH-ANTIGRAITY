"""Build and audit an electricity-only ASHRAE dataset.

This Phase 2 script reads the original ASHRAE CSV files without modifying them,
keeps meter 0 observations, rejects negative targets, preserves zero targets,
and left-joins building metadata and hourly weather. It writes Parquet when
PyArrow is usable and otherwise writes the explicitly supported CSV fallback.

Run from the repository root:
    python scripts/build_electricity_dataset.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

TRAIN = RAW / "train.csv"
WEATHER = RAW / "weather_train.csv"
BUILDINGS = RAW / "building_metadata.csv"
PARQUET_OUTPUT = PROCESSED / "electricity_processed.parquet"
CSV_OUTPUT = PROCESSED / "electricity_processed.csv"
JSON_REPORT = REPORTS / "electricity_dataset_audit.json"
MD_REPORT = REPORTS / "electricity_dataset_audit.md"

CHUNK_SIZE = 500_000
OBSERVATION_KEY = ["building_id", "meter", "timestamp"]
WEATHER_KEY = ["site_id", "timestamp"]
EXPECTED_COLUMNS = [
    "building_id", "meter", "timestamp", "meter_reading", "site_id",
    "primary_use", "square_feet", "year_built", "floor_count",
    "air_temperature", "cloud_coverage", "dew_temperature",
    "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
]


def _required_files() -> None:
    missing = [str(path) for path in (TRAIN, WEATHER, BUILDINGS) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing original ASHRAE input files: {missing}")


def _validate_lookup_keys(buildings: pd.DataFrame, weather: pd.DataFrame) -> None:
    if buildings["building_id"].isna().any() or not buildings["building_id"].is_unique:
        raise ValueError("Building metadata must have unique, non-null building_id values.")
    if weather[WEATHER_KEY].isna().any(axis=None) or weather.duplicated(WEATHER_KEY).any():
        raise ValueError("Weather must have unique, non-null (site_id, timestamp) keys.")


def _parquet_support() -> tuple[Any | None, Any | None, str | None]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        return pa, pq, None
    except (ImportError, OSError) as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def build_electricity_dataset() -> dict[str, Any]:
    _required_files()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    buildings = pd.read_csv(BUILDINGS)
    weather = pd.read_csv(WEATHER, parse_dates=["timestamp"])
    _validate_lookup_keys(buildings, weather)

    pa, pq, parquet_error = _parquet_support()
    use_parquet = pa is not None and pq is not None
    output = PARQUET_OUTPUT if use_parquet else CSV_OUTPUT
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    writer = None
    raw_rows = meter_zero_rows = negative_rejected = zero_preserved = output_rows = 0
    metadata_unmatched = weather_unmatched = 0
    missing = {column: 0 for column in EXPECTED_COLUMNS}
    building_ids: set[int] = set()
    site_ids: set[int] = set()
    key_hashes: list[np.ndarray] = []
    row_hashes: list[np.ndarray] = []
    date_min: pd.Timestamp | None = None
    date_max: pd.Timestamp | None = None
    numeric_columns: list[str] | None = None
    numeric_state: dict[str, dict[str, float | int]] = {}

    try:
        for chunk in pd.read_csv(TRAIN, chunksize=CHUNK_SIZE, parse_dates=["timestamp"]):
            raw_rows += len(chunk)
            electricity = chunk.loc[chunk["meter"].eq(0)].copy()
            meter_zero_rows += len(electricity)
            negative = electricity["meter_reading"].lt(0)
            negative_rejected += int(negative.sum())
            electricity = electricity.loc[~negative]
            zero_preserved += int(electricity["meter_reading"].eq(0).sum())
            if electricity.empty:
                continue

            merged = electricity.merge(
                buildings, on="building_id", how="left", validate="many_to_one",
                indicator="_metadata_merge", sort=False,
            )
            metadata_unmatched += int(merged["_metadata_merge"].eq("left_only").sum())
            merged.drop(columns="_metadata_merge", inplace=True)
            merged = merged.merge(
                weather, on=WEATHER_KEY, how="left", validate="many_to_one",
                indicator="_weather_merge", sort=False,
            )
            weather_unmatched += int(merged["_weather_merge"].eq("left_only").sum())
            merged.drop(columns="_weather_merge", inplace=True)
            merged = merged[EXPECTED_COLUMNS]
            if len(merged) != len(electricity):
                raise RuntimeError("A merge changed the filtered electricity row count.")

            output_rows += len(merged)
            building_ids.update(int(value) for value in merged["building_id"].dropna().unique())
            site_ids.update(int(value) for value in merged["site_id"].dropna().unique())
            current_min, current_max = merged["timestamp"].min(), merged["timestamp"].max()
            date_min = current_min if date_min is None else min(date_min, current_min)
            date_max = current_max if date_max is None else max(date_max, current_max)
            for column, count in merged.isna().sum().items():
                missing[column] += int(count)

            key_hashes.append(pd.util.hash_pandas_object(merged[OBSERVATION_KEY], index=False).to_numpy())
            row_hashes.append(pd.util.hash_pandas_object(merged, index=False).to_numpy())

            if numeric_columns is None:
                numeric_columns = merged.select_dtypes(include=[np.number]).columns.tolist()
                numeric_state = {
                    column: {"count": 0, "sum": 0.0, "sum_squares": 0.0, "min": math.inf, "max": -math.inf}
                    for column in numeric_columns
                }
            for column in numeric_columns:
                values = merged[column].dropna().astype("float64").to_numpy()
                if not len(values):
                    continue
                state = numeric_state[column]
                state["count"] += len(values)
                state["sum"] += float(values.sum())
                state["sum_squares"] += float(np.square(values).sum())
                state["min"] = min(float(state["min"]), float(values.min()))
                state["max"] = max(float(state["max"]), float(values.max()))

            if use_parquet:
                table = pa.Table.from_pandas(merged, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary, table.schema, compression="snappy")
                writer.write_table(table)
            else:
                merged.to_csv(temporary, mode="a", index=False, header=not temporary.exists())
    except Exception:
        if writer is not None:
            writer.close()
            writer = None
        if temporary.exists():
            temporary.unlink()
        raise
    finally:
        if writer is not None:
            writer.close()

    if output_rows == 0:
        raise RuntimeError("No valid electricity rows were found.")
    if output.exists():
        output.unlink()
    temporary.replace(output)

    def duplicate_count(parts: list[np.ndarray]) -> int:
        hashes = np.concatenate(parts)
        hashes.sort()
        return int(np.count_nonzero(hashes[1:] == hashes[:-1]))

    statistics: dict[str, dict[str, Any]] = {}
    for column, state in numeric_state.items():
        count = int(state["count"])
        mean = float(state["sum"]) / count if count else math.nan
        variance = max(float(state["sum_squares"]) / count - mean * mean, 0.0) if count else math.nan
        statistics[column] = {
            "count": count,
            "mean": _json_value(mean),
            "std_population": _json_value(math.sqrt(variance)),
            "min": _json_value(state["min"]),
            "max": _json_value(state["max"]),
        }

    audit = {
        "scope": "Original ASHRAE training data filtered to meter == 0; no model training",
        "source_files": [str(path.relative_to(ROOT)).replace("\\", "/") for path in (TRAIN, WEATHER, BUILDINGS)],
        "output": {
            "path": str(output.relative_to(ROOT)).replace("\\", "/"),
            "format": "parquet" if use_parquet else "csv",
            "file_size_bytes": output.stat().st_size,
            "parquet_fallback_reason": parquet_error,
        },
        "counts": {
            "source_train_rows": raw_rows,
            "source_meter_zero_rows": meter_zero_rows,
            "negative_readings_rejected": negative_rejected,
            "zero_readings_preserved": zero_preserved,
            "electricity_rows": output_rows,
            "buildings": len(building_ids),
            "sites": len(site_ids),
        },
        "date_range": {"minimum": _json_value(date_min), "maximum": _json_value(date_max)},
        "duplicates": {
            "observation_key_columns": OBSERVATION_KEY,
            "duplicate_observation_keys": duplicate_count(key_hashes),
            "duplicate_full_rows": duplicate_count(row_hashes),
            "method": "Exact pandas 64-bit row hashes; collision risk is negligible",
        },
        "merge_quality": {
            "building_metadata_unmatched_rows": metadata_unmatched,
            "weather_unmatched_rows": weather_unmatched,
        },
        "missing_values": missing,
        "statistics": statistics,
        "integrity": {
            "meter_is_zero_only": True,
            "negative_readings_remaining": 0,
            "zero_readings_preserved": True,
            "filtered_row_accounting_passed": meter_zero_rows == negative_rejected + output_rows,
            "original_files_modified": False,
            "model_trained": False,
        },
    }
    JSON_REPORT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    write_markdown(audit)
    return audit


def write_markdown(audit: dict[str, Any]) -> None:
    counts = audit["counts"]
    output = audit["output"]
    duplicates = audit["duplicates"]
    missing_rows = "\n".join(
        f"| `{column}` | {count:,} | {100 * count / counts['electricity_rows']:.4f}% |"
        for column, count in audit["missing_values"].items()
    )
    statistic_rows = "\n".join(
        f"| `{column}` | {values['count']:,} | {values['mean']:.6g} | {values['std_population']:.6g} | {values['min']:.6g} | {values['max']:.6g} |"
        for column, values in audit["statistics"].items()
    )
    fallback = (
        f"PyArrow was unavailable (`{output['parquet_fallback_reason']}`), so the requested CSV fallback was used."
        if output["format"] == "csv" else "PyArrow was available, so Snappy-compressed Parquet was written."
    )
    report = f"""# Electricity-Only Dataset Audit

## Executive summary

The original ASHRAE training observations were filtered to `meter == 0`, negative readings were rejected, zero readings were retained, and building metadata plus hourly site weather were merged with validated many-to-one left joins. The result contains **{counts['electricity_rows']:,} electricity rows**, **{counts['buildings']:,} buildings**, and **{counts['sites']:,} sites**. No model was trained and no original file was modified.

## Output

- Dataset: `{output['path']}`
- Format: **{output['format'].upper()}**
- Size: **{output['file_size_bytes'] / 2**20:,.2f} MiB**
- Format decision: {fallback}

## Filtering and row counts

| Measure | Count |
| --- | ---: |
| Original training rows scanned | {counts['source_train_rows']:,} |
| Original `meter == 0` rows | {counts['source_meter_zero_rows']:,} |
| Negative readings rejected | {counts['negative_readings_rejected']:,} |
| Zero readings preserved | {counts['zero_readings_preserved']:,} |
| Final electricity rows | {counts['electricity_rows']:,} |
| Unique buildings | {counts['buildings']:,} |
| Unique sites | {counts['sites']:,} |

## Date range

- Minimum timestamp: **{audit['date_range']['minimum']}**
- Maximum timestamp: **{audit['date_range']['maximum']}**

## Merge quality

| Join | Unmatched output rows |
| --- | ---: |
| Building metadata | {audit['merge_quality']['building_metadata_unmatched_rows']:,} |
| Weather | {audit['merge_quality']['weather_unmatched_rows']:,} |

Unmatched rows are preserved by the left joins and appear as missing metadata or weather values.

## Missing values

| Column | Missing cells | Percent |
| --- | ---: | ---: |
{missing_rows}

## Duplicates

| Measure | Count |
| --- | ---: |
| Duplicate (`building_id`, `meter`, `timestamp`) keys | {duplicates['duplicate_observation_keys']:,} |
| Duplicate complete rows | {duplicates['duplicate_full_rows']:,} |

Duplicate detection used exact pandas 64-bit row hashes across the complete filtered output.

## Numeric statistics

| Column | Non-null count | Mean | Population std. dev. | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
{statistic_rows}

## Integrity and scope

- Output contains only meter code 0: **passed**
- Negative readings remaining: **0**
- Zero readings preserved: **passed**
- Filtered row accounting: **{'passed' if audit['integrity']['filtered_row_accounting_passed'] else 'failed'}**
- Original ASHRAE files modified: **no**
- Production model or manifest modified: **no**
- Model training performed: **no**
"""
    MD_REPORT.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    result = build_electricity_dataset()
    print(json.dumps({"output": result["output"], "counts": result["counts"], "integrity": result["integrity"]}, indent=2))
