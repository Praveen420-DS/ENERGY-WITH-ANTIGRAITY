# Week 2 Task 2.2 — Data Preprocessing Report

## Executive Summary

Only the merged Task 2.1 dataset was preprocessed. Missing values were imputed using deterministic, documented strategies derived from the merged data itself. The output retains all **20,216,100 rows**, the original **16 columns**, their order and data types. No rows were removed, no features were created, and no model was trained.

## Input and Scope

- Input: `data/processed/merged_energy_data.parquet`
- Output: `data/processed/clean_dataset.parquet` (147.78 MB)
- Raw datasets: unchanged and not used as preprocessing inputs
- Target: `meter_reading` remained unchanged; it had no missing or impossible negative values

## Missing-Value Analysis

| Column | Missing before | Before (%) | Missing after |
| --- | ---: | ---: | ---: |
| `year_built` | 12,127,645 | 59.990% | 0 |
| `floor_count` | 16,709,167 | 82.653% | 0 |
| `air_temperature` | 96,658 | 0.478% | 0 |
| `cloud_coverage` | 8,825,365 | 43.655% | 0 |
| `dew_temperature` | 100,140 | 0.495% | 0 |
| `precip_depth_1_hr` | 3,749,023 | 18.545% | 0 |
| `sea_level_pressure` | 1,231,669 | 6.093% | 0 |
| `wind_direction` | 1,449,048 | 7.168% | 0 |
| `wind_speed` | 143,676 | 0.711% | 0 |

All identifier, target, timestamp, primary-use and square-foot fields were already complete.

## Missing-Value Decisions and Justification

### Static building metadata

- `year_built`: primary-use median, then global median (**1970.0**) if a category has no observed value; rounded to a whole year.
- `floor_count`: primary-use median, then global median (**3.0**) if needed; rounded to a whole floor.

These fields are constant building attributes. Primary use supplies a defensible peer group while the global fallback guarantees completeness. Median statistics are robust to extreme buildings. No indicator or derived column was added.

### Weather measurements

For each of the seven weather columns, missing values were filled by linear interpolation in chronological order **within the same site**. Edge/all-missing cases fall back to the site median and finally the global median. This preserves site-specific climate context and temporal continuity without borrowing measurements across sites. Interpolation applies only to missing cells; observed values are retained.

Global fallbacks used only when earlier levels could not provide a value:

| Weather column | Global median fallback |
| --- | ---: |
| `air_temperature` | 15.0000 |
| `cloud_coverage` | 2.0000 |
| `dew_temperature` | 8.2000 |
| `precip_depth_1_hr` | 0.0000 |
| `sea_level_pressure` | 1016.4000 |
| `wind_direction` | 190.0000 |
| `wind_speed` | 3.1000 |

## Consistency and Impossible-Record Review

| Check | Count |
| --- | ---: |
| `weather_value_conflicts` | 0 |
| `negative_meter_reading` | 0 |
| `nonpositive_square_feet` | 0 |
| `negative_building_id` | 0 |
| `negative_site_id` | 0 |
| `invalid_meter_code` | 0 |
| `invalid_timestamp` | 0 |
| `air_temperature_outside_-100_70` | 0 |
| `negative_wind_speed` | 0 |
| `wind_direction_outside_0_360` | 0 |

No impossible core records were identified, so **zero records were removed**. Broad physical range checks also passed after imputation. Potential statistical outliers and zero target readings were retained because they are not inherently impossible and outlier treatment is outside this task.

## Remaining Missing Values

Remaining missing cells: **0**.

## Preprocessing Summary

- Row count preserved: **True**
- Column order preserved: **True**
- Column types preserved: **True**
- Records removed: **0**
- New features added: **0**
- Integrity status: **PASSED**

Task 2.2 stops here. Feature engineering and model training were not started.
