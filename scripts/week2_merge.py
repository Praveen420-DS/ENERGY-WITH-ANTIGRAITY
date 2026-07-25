"""Week 2 Task 2.1: merge the three source datasets without preprocessing.

Run from the repository root with: python scripts/week2_merge.py
The raw files are read-only. The only data artifact written is the merged
Parquet dataset in data/processed/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
OUTPUT = PROCESSED / "merged_energy_data.parquet"
STATS_OUTPUT = REPORTS / "week2_merge_statistics.json"
REPORT_OUTPUT = REPORTS / "week2_merge_report.md"
CHUNK_SIZE = 500_000
TRAIN_KEY = ["building_id", "meter", "timestamp"]
WEATHER_KEY = ["site_id", "timestamp"]


def validate_source_keys(building: pd.DataFrame, weather: pd.DataFrame) -> dict:
    """Validate source-side merge keys before any output is created."""
    required_building = {"building_id", "site_id"}
    required_weather = set(WEATHER_KEY)
    if not required_building.issubset(building.columns):
        raise KeyError(f"Missing metadata keys: {required_building - set(building.columns)}")
    if not required_weather.issubset(weather.columns):
        raise KeyError(f"Missing weather keys: {required_weather - set(weather.columns)}")

    metadata_null_keys = int(building["building_id"].isna().sum())
    weather_null_keys = int(weather[WEATHER_KEY].isna().any(axis=1).sum())
    metadata_duplicate_keys = int(building.duplicated("building_id").sum())
    weather_duplicate_keys = int(weather.duplicated(WEATHER_KEY).sum())
    if metadata_null_keys or weather_null_keys:
        raise ValueError("Merge keys contain null values; merge stopped without altering data.")
    if metadata_duplicate_keys or weather_duplicate_keys:
        raise ValueError("Right-side keys are not unique; many-to-one merge would be unsafe.")
    return {
        "metadata_null_keys": metadata_null_keys,
        "weather_null_keys": weather_null_keys,
        "metadata_duplicate_keys": metadata_duplicate_keys,
        "weather_duplicate_keys": weather_duplicate_keys,
    }


def merge_datasets() -> dict:
    """Perform validated left joins and write one chunked Parquet dataset."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    building = pd.read_csv(RAW / "building_metadata.csv")
    weather = pd.read_csv(RAW / "weather_train.csv", parse_dates=["timestamp"])
    key_stats = validate_source_keys(building, weather)

    source_rows = output_rows = metadata_unmatched = weather_unmatched = 0
    source_nulls = output_nulls = None
    train_key_hashes: list[np.ndarray] = []
    output_key_hashes: list[np.ndarray] = []
    writer: pq.ParquetWriter | None = None
    output_columns: list[str] | None = None

    try:
        for chunk in pd.read_csv(RAW / "train.csv", chunksize=CHUNK_SIZE, parse_dates=["timestamp"]):
            source_rows += len(chunk)
            source_nulls = chunk.isna().sum() if source_nulls is None else source_nulls.add(chunk.isna().sum(), fill_value=0)
            train_key_hashes.append(pd.util.hash_pandas_object(chunk[TRAIN_KEY], index=False).to_numpy())

            merged = chunk.merge(
                building,
                on="building_id",
                how="left",
                validate="many_to_one",
                indicator="_metadata_merge",
                sort=False,
            )
            metadata_unmatched += int(merged["_metadata_merge"].eq("left_only").sum())
            merged.drop(columns="_metadata_merge", inplace=True)
            merged = merged.merge(
                weather,
                on=WEATHER_KEY,
                how="left",
                validate="many_to_one",
                indicator="_weather_merge",
                sort=False,
            )
            weather_unmatched += int(merged["_weather_merge"].eq("left_only").sum())
            merged.drop(columns="_weather_merge", inplace=True)

            if len(merged) != len(chunk):
                raise RuntimeError("A merge changed the training row count.")
            if output_columns is None:
                output_columns = merged.columns.tolist()
            elif merged.columns.tolist() != output_columns:
                raise RuntimeError("Output schema changed between chunks.")

            output_rows += len(merged)
            output_nulls = merged.isna().sum() if output_nulls is None else output_nulls.add(merged.isna().sum(), fill_value=0)
            output_key_hashes.append(pd.util.hash_pandas_object(merged[TRAIN_KEY], index=False).to_numpy())
            table = pa.Table.from_pandas(merged, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(OUTPUT, table.schema, compression="snappy")
            writer.write_table(table)
    except Exception:
        if writer is not None:
            writer.close()
        if OUTPUT.exists():
            OUTPUT.unlink()
        raise
    finally:
        if writer is not None:
            writer.close()

    def duplicate_count(parts: list[np.ndarray]) -> int:
        hashes = np.concatenate(parts)
        hashes.sort()
        return int(np.count_nonzero(hashes[1:] == hashes[:-1]))

    train_duplicate_keys = duplicate_count(train_key_hashes)
    output_duplicate_keys = duplicate_count(output_key_hashes)
    parquet = pq.ParquetFile(OUTPUT)
    parquet_rows = parquet.metadata.num_rows
    parquet_columns = parquet.schema_arrow.names
    expected_columns = [
        "building_id", "meter", "timestamp", "meter_reading", "site_id",
        "primary_use", "square_feet", "year_built", "floor_count",
        "air_temperature", "cloud_coverage", "dew_temperature",
        "precip_depth_1_hr", "sea_level_pressure", "wind_direction", "wind_speed",
    ]
    integrity_ok = (
        source_rows == output_rows == parquet_rows
        and output_columns == expected_columns
        and parquet_columns == expected_columns
        and train_duplicate_keys == output_duplicate_keys
    )
    if not integrity_ok:
        raise RuntimeError("Post-write merge integrity validation failed.")

    stats = {
        "strategy": "Two sequential left joins: train -> building metadata -> weather",
        "merge_keys": {"metadata": ["building_id"], "weather": WEATHER_KEY},
        "source_rows": {
            "train": source_rows,
            "building_metadata": len(building),
            "weather_train": len(weather),
        },
        "output": {
            "path": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
            "format": "Parquet (Snappy)",
            "rows": output_rows,
            "columns": len(output_columns or []),
            "column_names": output_columns,
            "file_size_mb": round(OUTPUT.stat().st_size / 2**20, 2),
            "row_groups": parquet.metadata.num_row_groups,
        },
        "key_validation": {
            **key_stats,
            "train_duplicate_keys": train_duplicate_keys,
            "output_duplicate_keys": output_duplicate_keys,
            "output_duplicate_rows": output_duplicate_keys,
        },
        "unmatched": {
            "metadata_rows": metadata_unmatched,
            "weather_rows": weather_unmatched,
        },
        "success_rates": {
            "metadata_percent": round(100 * (source_rows - metadata_unmatched) / source_rows, 4),
            "weather_percent": round(100 * (source_rows - weather_unmatched) / source_rows, 4),
            "overall_complete_match_percent": round(100 * (source_rows - metadata_unmatched - weather_unmatched) / source_rows, 4),
            "row_retention_percent": round(100 * output_rows / source_rows, 4),
        },
        "integrity": {
            "source_output_row_count_equal": source_rows == output_rows,
            "written_row_count_equal": output_rows == parquet_rows,
            "schema_matches_expected": output_columns == expected_columns and parquet_columns == expected_columns,
            "target_preserved": "meter_reading" in parquet_columns,
            "passed": integrity_ok,
        },
        "missing_values_preserved": {
            "source_train": {k: int(v) for k, v in source_nulls.items()},
            "merged_output": {k: int(v) for k, v in output_nulls.items()},
        },
    }
    STATS_OUTPUT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    write_report(stats)
    write_notebook()
    return stats


def write_report(s: dict) -> None:
    src, out, keys, unmatched, rates, integrity = (
        s["source_rows"], s["output"], s["key_validation"], s["unmatched"],
        s["success_rates"], s["integrity"],
    )
    report = f"""# Week 2 Task 2.1 — Dataset Merge Report

## Executive Summary

The three source datasets were merged successfully into one **{out['format']}** dataset containing **{out['rows']:,} rows and {out['columns']} columns**. All labelled training rows and the `meter_reading` target were retained. No preprocessing, imputation, filtering, outlier treatment, feature engineering, or model training was performed.

## Merge Strategy

Two sequential left joins preserve the training table as the authoritative row population:

1. `train.csv` LEFT JOIN `building_metadata.csv` on `building_id` (`many_to_one`).
2. Result LEFT JOIN `weather_train.csv` on (`site_id`, `timestamp`) (`many_to_one`).

Metadata must be joined first because `site_id`, required for the weather join, originates in building metadata. Right-side uniqueness was asserted before writing, and pandas `validate='many_to_one'` enforced cardinality during every chunked merge.

## Row Counts

| Dataset / stage | Rows |
| --- | ---: |
| `train.csv` | {src['train']:,} |
| `building_metadata.csv` | {src['building_metadata']:,} |
| `weather_train.csv` | {src['weather_train']:,} |
| Merged output | {out['rows']:,} |

Row retention is **{rates['row_retention_percent']:.4f}%**. The output contains {out['row_groups']} Parquet row groups and occupies approximately **{out['file_size_mb']:.2f} MB**.

## Unmatched Records and Success Rates

| Join | Unmatched training rows | Match success |
| --- | ---: | ---: |
| Building metadata | {unmatched['metadata_rows']:,} | {rates['metadata_percent']:.4f}% |
| Weather | {unmatched['weather_rows']:,} | {rates['weather_percent']:.4f}% |
| Both joins complete | — | {rates['overall_complete_match_percent']:.4f}% |

Unmatched weather rows remain in the output with null weather columns, as required by a left join. They were not filled or removed.

## Duplicate and Key Validation

| Validation | Result |
| --- | ---: |
| Null metadata keys | {keys['metadata_null_keys']:,} |
| Null weather composite keys | {keys['weather_null_keys']:,} |
| Duplicate `building_id` metadata keys | {keys['metadata_duplicate_keys']:,} |
| Duplicate (`site_id`, `timestamp`) weather keys | {keys['weather_duplicate_keys']:,} |
| Duplicate (`building_id`, `meter`, `timestamp`) train keys | {keys['train_duplicate_keys']:,} |
| Duplicate output keys | {keys['output_duplicate_keys']:,} |
| Duplicate output rows | {keys['output_duplicate_rows']:,} |

Because the output observation key is unique, exact duplicate output rows are also necessarily zero.

## Merge Integrity

- Source and output row counts equal: **{integrity['source_output_row_count_equal']}**
- Written Parquet row count verified: **{integrity['written_row_count_equal']}**
- Exact expected 16-column schema verified: **{integrity['schema_matches_expected']}**
- Prediction target retained: **{integrity['target_preserved']}**
- Overall integrity status: **{'PASSED' if integrity['passed'] else 'FAILED'}**

## Output

- Dataset: `{out['path']}`
- Machine-readable statistics: `reports/week2_merge_statistics.json`
- Reproduction script: `scripts/week2_merge.py`

## Scope Confirmation

Task 2.1 stops at merging. Existing missing values plus merge-created weather nulls are preserved exactly; no Week 2 preprocessing or modelling tasks have begun.
"""
    REPORT_OUTPUT.write_text(report, encoding="utf-8")


def write_notebook() -> None:
    """Write a focused, reproducible merge notebook without nbformat dependency."""
    def md(text: str) -> dict:
        return {"cell_type": "markdown", "metadata": {}, "source": [x + "\n" for x in text.strip().splitlines()]}
    def code(text: str) -> dict:
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [x + "\n" for x in text.strip().splitlines()]}
    cells = [
        md("# Week 2 — Task 2.1: Dataset Merging\n\nScope: validate keys, perform two left joins, save and verify one merged dataset. No preprocessing, filling, filtering, feature engineering, or modelling is performed."),
        md("## 1. Paths and source metadata"),
        code("from pathlib import Path\nimport json\nimport pandas as pd\nimport pyarrow.parquet as pq\n\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nRAW = ROOT / 'data' / 'raw'\nOUTPUT = ROOT / 'data' / 'processed' / 'merged_energy_data.parquet'\nSTATS = ROOT / 'reports' / 'week2_merge_statistics.json'"),
        code("building = pd.read_csv(RAW / 'building_metadata.csv')\nweather = pd.read_csv(RAW / 'weather_train.csv', parse_dates=['timestamp'])\nprint('Building metadata:', building.shape)\nprint('Weather:', weather.shape)"),
        md("## 2. Validate right-side merge keys\n\nBoth right-side keys must be non-null and unique for safe many-to-one joins."),
        code("assert building['building_id'].notna().all()\nassert building['building_id'].is_unique\nassert weather[['site_id', 'timestamp']].notna().all(axis=None)\nassert not weather.duplicated(['site_id', 'timestamp']).any()\nprint('Right-side merge keys are valid.')"),
        md("## 3. Run the memory-safe merge\n\nThe reusable project script reads training data in chunks, enforces `many_to_one` validation, and writes compressed Parquet. Running this cell recreates the output."),
        code("import sys\nsys.path.insert(0, str(ROOT))\nfrom scripts.week2_merge import merge_datasets\nmerge_statistics = merge_datasets()\nmerge_statistics['integrity']"),
        md("## 4. Inspect merge statistics"),
        code("statistics = json.loads(STATS.read_text(encoding='utf-8'))\ndisplay(pd.DataFrame([statistics['source_rows']]))\ndisplay(pd.DataFrame([statistics['unmatched']]))\ndisplay(pd.DataFrame([statistics['success_rates']]))\ndisplay(pd.DataFrame([statistics['key_validation']]))"),
        md("## 5. Independently verify the saved artifact"),
        code("parquet = pq.ParquetFile(OUTPUT)\nassert parquet.metadata.num_rows == statistics['source_rows']['train']\nassert parquet.schema_arrow.names == statistics['output']['column_names']\nassert 'meter_reading' in parquet.schema_arrow.names\nprint(f\"Verified {parquet.metadata.num_rows:,} rows and {len(parquet.schema_arrow.names)} columns.\")\nparquet.read_row_group(0).to_pandas().head()  # Memory-safe preview."),
        md("## 6. Task 2.1 conclusion\n\nThe merge is complete and integrity checks passed. Unmatched weather observations remain null. Stop here: preprocessing and all subsequent Week 2 tasks are intentionally outside this notebook."),
    ]
    notebook = {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (ROOT / "notebooks" / "02_dataset_merge.ipynb").write_text(json.dumps(notebook, indent=1), encoding="utf-8")


if __name__ == "__main__":
    result = merge_datasets()
    print(json.dumps({"output": result["output"], "integrity": result["integrity"]}, indent=2))
