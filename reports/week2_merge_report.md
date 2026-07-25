# Week 2 Task 2.1 — Dataset Merge Report

## Executive Summary

The three source datasets were merged successfully into one **Parquet (Snappy)** dataset containing **20,216,100 rows and 16 columns**. All labelled training rows and the `meter_reading` target were retained. No preprocessing, imputation, filtering, outlier treatment, feature engineering, or model training was performed.

## Merge Strategy

Two sequential left joins preserve the training table as the authoritative row population:

1. `train.csv` LEFT JOIN `building_metadata.csv` on `building_id` (`many_to_one`).
2. Result LEFT JOIN `weather_train.csv` on (`site_id`, `timestamp`) (`many_to_one`).

Metadata must be joined first because `site_id`, required for the weather join, originates in building metadata. Right-side uniqueness was asserted before writing, and pandas `validate='many_to_one'` enforced cardinality during every chunked merge.

## Row Counts

| Dataset / stage | Rows |
| --- | ---: |
| `train.csv` | 20,216,100 |
| `building_metadata.csv` | 1,449 |
| `weather_train.csv` | 139,773 |
| Merged output | 20,216,100 |

Row retention is **100.0000%**. The output contains 41 Parquet row groups and occupies approximately **146.07 MB**.

## Unmatched Records and Success Rates

| Join | Unmatched training rows | Match success |
| --- | ---: | ---: |
| Building metadata | 0 | 100.0000% |
| Weather | 90,495 | 99.5524% |
| Both joins complete | — | 99.5524% |

Unmatched weather rows remain in the output with null weather columns, as required by a left join. They were not filled or removed.

## Duplicate and Key Validation

| Validation | Result |
| --- | ---: |
| Null metadata keys | 0 |
| Null weather composite keys | 0 |
| Duplicate `building_id` metadata keys | 0 |
| Duplicate (`site_id`, `timestamp`) weather keys | 0 |
| Duplicate (`building_id`, `meter`, `timestamp`) train keys | 0 |
| Duplicate output keys | 0 |
| Duplicate output rows | 0 |

Because the output observation key is unique, exact duplicate output rows are also necessarily zero.

## Merge Integrity

- Source and output row counts equal: **True**
- Written Parquet row count verified: **True**
- Exact expected 16-column schema verified: **True**
- Prediction target retained: **True**
- Overall integrity status: **PASSED**

## Output

- Dataset: `data/processed/merged_energy_data.parquet`
- Machine-readable statistics: `reports/week2_merge_statistics.json`
- Reproduction script: `scripts/week2_merge.py`

## Scope Confirmation

Task 2.1 stops at merging. Existing missing values plus merge-created weather nulls are preserved exactly; no Week 2 preprocessing or modelling tasks have begun.
