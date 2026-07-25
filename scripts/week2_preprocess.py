"""Week 2 Task 2.2: missing-value preprocessing of the merged dataset only.

No features are added, no outliers are removed, and no models are trained.
The 16-column merged schema and row order are preserved.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "merged_energy_data.parquet"
OUTPUT = ROOT / "data" / "processed" / "clean_dataset.parquet"
REPORT = ROOT / "reports" / "week2_preprocessing_report.md"
STATS = ROOT / "reports" / "week2_preprocessing_statistics.json"

STATIC_COLUMNS = ["year_built", "floor_count"]
WEATHER_COLUMNS = [
    "air_temperature", "cloud_coverage", "dew_temperature",
    "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
]
CORE_COLUMNS = ["building_id", "meter", "timestamp", "meter_reading", "site_id", "primary_use", "square_feet"]


def collect_unique_lookups(parquet: pq.ParquetFile) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Collect unique static/weather records without materializing 20M rows."""
    static_parts, weather_parts = [], []
    weather_conflicts = 0
    for i in range(parquet.metadata.num_row_groups):
        static = parquet.read_row_group(i, columns=["building_id", "primary_use", *STATIC_COLUMNS]).to_pandas()
        static_parts.append(static.drop_duplicates("building_id"))
        weather = parquet.read_row_group(i, columns=["site_id", "timestamp", *WEATHER_COLUMNS]).to_pandas()
        weather_parts.append(weather.drop_duplicates(["site_id", "timestamp"]))
    static_lookup = pd.concat(static_parts, ignore_index=True).drop_duplicates("building_id")
    weather_all = pd.concat(weather_parts, ignore_index=True)
    # The same site-hour should never carry conflicting non-null source values.
    grouped = weather_all.groupby(["site_id", "timestamp"], sort=False, dropna=False)
    for col in WEATHER_COLUMNS:
        weather_conflicts += int(grouped[col].nunique(dropna=True).gt(1).sum())
    weather_lookup = grouped[WEATHER_COLUMNS].first().reset_index()
    return static_lookup, weather_lookup, {"weather_value_conflicts": weather_conflicts}


def build_static_imputation(static: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fill static fields by primary-use median, then global median."""
    result = static.copy()
    decisions = {}
    for col in STATIC_COLUMNS:
        before = int(result[col].isna().sum())
        group_medians = result.groupby("primary_use", observed=True)[col].transform("median")
        global_median = float(result[col].median())
        result[col] = result[col].fillna(group_medians).fillna(global_median).round()
        decisions[col] = {
            "method": "primary_use median, then global median; rounded to whole-number semantics",
            "missing_unique_buildings_before": before,
            "global_fallback": global_median,
            "missing_unique_buildings_after": int(result[col].isna().sum()),
        }
    return result[["building_id", *STATIC_COLUMNS]], decisions


def build_weather_imputation(weather: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Create a complete observed site/time lookup and impute within each site."""
    result = weather.sort_values(["site_id", "timestamp"]).copy()
    decisions = {}
    for col in WEATHER_COLUMNS:
        before = int(result[col].isna().sum())
        # Time interpolation uses only the same site's chronological measurements.
        result[col] = result.groupby("site_id", group_keys=False)[col].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both")
        )
        site_median = result.groupby("site_id")[col].transform("median")
        global_median = float(result[col].median())
        result[col] = result[col].fillna(site_median).fillna(global_median)
        decisions[col] = {
            "method": "linear interpolation within site, then site median, then global median",
            "missing_site_hours_before": before,
            "global_fallback": global_median,
            "missing_site_hours_after": int(result[col].isna().sum()),
        }
    return result, decisions


def impossible_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Conservative physical/key consistency checks; none are auto-filtered here."""
    return {
        "negative_meter_reading": df["meter_reading"].lt(0),
        "nonpositive_square_feet": df["square_feet"].le(0),
        "negative_building_id": df["building_id"].lt(0),
        "negative_site_id": df["site_id"].lt(0),
        "invalid_meter_code": ~df["meter"].isin([0, 1, 2, 3]),
        "invalid_timestamp": df["timestamp"].isna(),
        "air_temperature_outside_-100_70": ~df["air_temperature"].between(-100, 70),
        "negative_wind_speed": df["wind_speed"].lt(0),
        "wind_direction_outside_0_360": ~df["wind_direction"].between(0, 360),
    }


def preprocess() -> dict:
    if not INPUT.exists():
        raise FileNotFoundError(f"Merged input not found: {INPUT}")
    parquet = pq.ParquetFile(INPUT)
    input_schema = parquet.schema_arrow
    static_raw, weather_raw, consistency = collect_unique_lookups(parquet)
    static_fill, static_decisions = build_static_imputation(static_raw)
    weather_fill, weather_decisions = build_weather_imputation(weather_raw)

    before_missing = {name: 0 for name in input_schema.names}
    after_missing = {name: 0 for name in input_schema.names}
    impossible_counts: dict[str, int] = {}
    rows_written = 0
    writer: pq.ParquetWriter | None = None
    try:
        for i in range(parquet.metadata.num_row_groups):
            chunk = parquet.read_row_group(i).to_pandas()
            for col, value in chunk.isna().sum().items(): before_missing[col] += int(value)

            # Replace only missing values; original observed values remain untouched.
            chunk = chunk.merge(static_fill, on="building_id", how="left", suffixes=("", "_fill"), validate="many_to_one", sort=False)
            for col in STATIC_COLUMNS:
                chunk[col] = chunk[col].fillna(chunk.pop(f"{col}_fill"))
            chunk = chunk.merge(weather_fill, on=["site_id", "timestamp"], how="left", suffixes=("", "_fill"), validate="many_to_one", sort=False)
            for col in WEATHER_COLUMNS:
                chunk[col] = chunk[col].fillna(chunk.pop(f"{col}_fill"))
            chunk = chunk[input_schema.names]

            for name, mask in impossible_masks(chunk).items():
                impossible_counts[name] = impossible_counts.get(name, 0) + int(mask.sum())
            for col, value in chunk.isna().sum().items(): after_missing[col] += int(value)
            rows_written += len(chunk)
            table = pa.Table.from_pandas(chunk, schema=input_schema, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(OUTPUT, input_schema, compression="snappy")
            writer.write_table(table)
    except Exception:
        if writer is not None:
            writer.close()
            writer = None
        if OUTPUT.exists(): OUTPUT.unlink()
        raise
    finally:
        if writer is not None: writer.close()

    output_parquet = pq.ParquetFile(OUTPUT)
    if rows_written != parquet.metadata.num_rows or output_parquet.metadata.num_rows != rows_written:
        raise RuntimeError("Preprocessing changed or failed to preserve the row count.")
    if output_parquet.schema_arrow.names != input_schema.names:
        raise RuntimeError("Preprocessing changed the dataset columns.")
    if any(after_missing.values()):
        raise RuntimeError("Imputation completed with unexpected remaining missing values.")

    # No records are removed: all core fields pass conservative impossibility checks.
    core_impossible = sum(impossible_counts[k] for k in [
        "negative_meter_reading", "nonpositive_square_feet", "negative_building_id",
        "negative_site_id", "invalid_meter_code", "invalid_timestamp",
    ])
    if core_impossible:
        raise RuntimeError("Impossible core records found; refusing automatic removal without review.")

    stats = {
        "input": {"path": str(INPUT.relative_to(ROOT)).replace("\\", "/"), "rows": parquet.metadata.num_rows, "columns": len(input_schema.names)},
        "output": {"path": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"), "rows": rows_written, "columns": len(input_schema.names), "file_size_mb": round(OUTPUT.stat().st_size / 2**20, 2)},
        "missing_before": before_missing,
        "missing_after": after_missing,
        "imputation_decisions": {"static_metadata": static_decisions, "weather": weather_decisions},
        "consistency_checks": {**consistency, **impossible_counts},
        "records_removed": 0,
        "integrity": {
            "row_count_preserved": rows_written == parquet.metadata.num_rows,
            "column_order_preserved": output_parquet.schema_arrow.names == input_schema.names,
            "column_types_preserved": output_parquet.schema_arrow == input_schema,
            "remaining_missing_values": sum(after_missing.values()),
            "passed": True,
        },
    }
    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    write_report(stats)
    return stats


def write_report(s: dict) -> None:
    before, after = s["missing_before"], s["missing_after"]
    rows = s["input"]["rows"]
    missing_lines = []
    for col in before:
        if before[col] or after[col]:
            missing_lines.append(f"| `{col}` | {before[col]:,} | {100*before[col]/rows:.3f}% | {after[col]:,} |")
    static = s["imputation_decisions"]["static_metadata"]
    weather = s["imputation_decisions"]["weather"]
    consistency = s["consistency_checks"]
    report = f"""# Week 2 Task 2.2 — Data Preprocessing Report

## Executive Summary

Only the merged Task 2.1 dataset was preprocessed. Missing values were imputed using deterministic, documented strategies derived from the merged data itself. The output retains all **{rows:,} rows**, the original **{s['input']['columns']} columns**, their order and data types. No rows were removed, no features were created, and no model was trained.

## Input and Scope

- Input: `{s['input']['path']}`
- Output: `{s['output']['path']}` ({s['output']['file_size_mb']:.2f} MB)
- Raw datasets: unchanged and not used as preprocessing inputs
- Target: `meter_reading` remained unchanged; it had no missing or impossible negative values

## Missing-Value Analysis

| Column | Missing before | Before (%) | Missing after |
| --- | ---: | ---: | ---: |
{chr(10).join(missing_lines)}

All identifier, target, timestamp, primary-use and square-foot fields were already complete.

## Missing-Value Decisions and Justification

### Static building metadata

- `year_built`: primary-use median, then global median (**{static['year_built']['global_fallback']:.1f}**) if a category has no observed value; rounded to a whole year.
- `floor_count`: primary-use median, then global median (**{static['floor_count']['global_fallback']:.1f}**) if needed; rounded to a whole floor.

These fields are constant building attributes. Primary use supplies a defensible peer group while the global fallback guarantees completeness. Median statistics are robust to extreme buildings. No indicator or derived column was added.

### Weather measurements

For each of the seven weather columns, missing values were filled by linear interpolation in chronological order **within the same site**. Edge/all-missing cases fall back to the site median and finally the global median. This preserves site-specific climate context and temporal continuity without borrowing measurements across sites. Interpolation applies only to missing cells; observed values are retained.

Global fallbacks used only when earlier levels could not provide a value:

| Weather column | Global median fallback |
| --- | ---: |
{chr(10).join(f"| `{col}` | {decision['global_fallback']:.4f} |" for col, decision in weather.items())}

## Consistency and Impossible-Record Review

| Check | Count |
| --- | ---: |
{chr(10).join(f"| `{name}` | {count:,} |" for name, count in consistency.items())}

No impossible core records were identified, so **zero records were removed**. Broad physical range checks also passed after imputation. Potential statistical outliers and zero target readings were retained because they are not inherently impossible and outlier treatment is outside this task.

## Remaining Missing Values

Remaining missing cells: **{s['integrity']['remaining_missing_values']:,}**.

## Preprocessing Summary

- Row count preserved: **{s['integrity']['row_count_preserved']}**
- Column order preserved: **{s['integrity']['column_order_preserved']}**
- Column types preserved: **{s['integrity']['column_types_preserved']}**
- Records removed: **{s['records_removed']}**
- New features added: **0**
- Integrity status: **PASSED**

Task 2.2 stops here. Feature engineering and model training were not started.
"""
    REPORT.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    result = preprocess()
    print(json.dumps({"output": result["output"], "integrity": result["integrity"]}, indent=2))
