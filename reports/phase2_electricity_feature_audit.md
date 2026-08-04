# Phase 2 Electricity Feature Audit

## Result

The pipeline produced **12,060,910 rows** with **45 model features** (43 numeric and 2 categorical). Meter code 0 was validated and `meter` was removed from predictors. No feature derives from the target, no model was trained, and the electricity unit remains unverified.

## Counts and integrity

| Measure | Value |
| --- | ---: |
| Input rows | 12,060,910 |
| Output rows | 12,060,910 |
| Zero targets preserved | 530,169 |
| Duplicate complete rows | 0 |
| Infinite values | 0 |
| Rows with unresolved weather | 0 |
| Invalid/missing square feet rows | 0 |
| Invalid/missing year built rows | 6,478,817 |
| Invalid/missing floor count rows | 9,096,083 |

## Weather missingness before treatment

| Feature | Missing rows |
| --- | ---: |
| `air_temperature` | 47,325 |
| `cloud_coverage` | 5,329,652 |
| `dew_temperature` | 49,091 |
| `precip_depth_1_hr` | 2,513,679 |
| `sea_level_pressure` | 1,018,383 |
| `wind_direction` | 678,715 |
| `wind_speed` | 66,795 |

## Missing values after deterministic treatment

Weather is fully resolved. Remaining missing values are retained building metadata and safe derived building features; model-time imputation must be fitted on training data only.

| Feature | Missing rows |
| --- | ---: |
| `year_built` | 6,470,035 |
| `floor_count` | 9,096,083 |
| `building_age` | 6,478,817 |
| `area_per_floor` | 9,096,083 |

## Leakage and preprocessing policy

- Weather ordering: site/month external partitions, sorted by site, timestamp, and building.
- Weather interpolation: causal forward carry only; never bidirectional.
- Fallbacks: site median, then global median, fitted only through `2016-08-31T23:59:59`.
- Missingness indicators preserve the original weather-null state.
- Target lags, rolling targets, target means, and future-aware aggregates: absent.
- Meter removed from predictors: **true**.
- Target-derived features: **false**.

## Artifact

- Output: `data\processed\electricity_features.csv`
- Size: 3,057.88 MiB
- SHA-256: `e1169ad3476b244f9c2e7e633a22a7f91e1014e9f808eb344d970e324e7cce64`
- Processing duration: 516.531 seconds
