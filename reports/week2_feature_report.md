# Week 2 Task 2.3 — Feature Engineering Report

## Objective and Input Summary

Create deterministic, model-ready predictors from `data/processed/clean_dataset.parquet` while retaining target, timestamp, identifiers and every original predictor. Input: **20,216,100 rows × 16 columns**; output: **20,216,100 rows × 46 columns**.

## Feature-Engineering Principles

Features use only timestamps and observed predictor columns. No target aggregate, target encoding, lag, rolling statistic, fitted encoder, scaling, split, outlier removal or model was created. Processing was chunked by Parquet row group, deterministic, and preserved row order. Cyclical sine/cosine pairs place adjacent clock/calendar endpoints near each other geometrically.

## Column Roles

| Role | Columns |
| --- | --- |
| Original predictors | `square_feet`, `year_built`, `floor_count`, `air_temperature`, `cloud_coverage`, `dew_temperature`, `precip_depth_1_hr`, `sea_level_pressure`, `wind_direction`, `wind_speed` |
| Engineered predictors | `hour`, `day_of_week`, `day_of_month`, `day_of_year`, `week_of_year`, `month`, `quarter`, `is_weekend`, `hour_sin`, `hour_cos`, `day_of_week_sin`, `day_of_week_cos`, `month_sin`, `month_cos`, `building_age_2016`, `log_square_feet`, `square_feet_per_floor`, `temperature_difference`, `relative_humidity`, `wind_direction_sin`, `wind_direction_cos`, `is_precipitating`, `is_freezing`, `is_hot`, `heating_degree_proxy`, `cooling_degree_proxy`, `log_square_feet_x_air_temperature`, `building_age_x_air_temperature`, `heating_degree_x_log_square_feet`, `cooling_degree_x_log_square_feet` |
| Identifiers | `building_id`, `site_id` |
| Categorical variables | `primary_use`, `meter`, `site_id`, `building_id` |
| Timestamp | `timestamp` (retained for chronological splitting) |
| Target | `meter_reading` (retained and byte-for-byte value validated) |

## Complete Feature Dictionary

| Feature | Source columns | Formula | Type | Expected range | Purpose |
| --- | --- | --- | --- | --- | --- |
| `hour` | `timestamp` | timestamp hour | `int8` | 0..23 | daily cycle |
| `day_of_week` | `timestamp` | Monday=0 through Sunday=6 | `int8` | 0..6 | weekly cycle |
| `day_of_month` | `timestamp` | calendar day | `int8` | 1..31 | within-month timing |
| `day_of_year` | `timestamp` | calendar ordinal day | `int16` | 1..366 | annual progression |
| `week_of_year` | `timestamp` | ISO week number | `int8` | 1..53 | annual weekly cycle |
| `month` | `timestamp` | calendar month | `int8` | 1..12 | seasonality |
| `quarter` | `timestamp` | calendar quarter | `int8` | 1..4 | coarse seasonality |
| `is_weekend` | `timestamp` | day_of_week >= 5 | `bool` | False..True | occupancy schedule proxy |
| `hour_sin` | `timestamp` | sin(2*pi*hour/24) | `float32` | -1..1 | continuous cyclical hour |
| `hour_cos` | `timestamp` | cos(2*pi*hour/24) | `float32` | -1..1 | continuous cyclical hour |
| `day_of_week_sin` | `timestamp` | sin(2*pi*day_of_week/7) | `float32` | -1..1 | continuous weekly cycle |
| `day_of_week_cos` | `timestamp` | cos(2*pi*day_of_week/7) | `float32` | -1..1 | continuous weekly cycle |
| `month_sin` | `timestamp` | sin(2*pi*(month-1)/12) | `float32` | -1..1 | continuous annual cycle |
| `month_cos` | `timestamp` | cos(2*pi*(month-1)/12) | `float32` | -1..1 | continuous annual cycle |
| `building_age_2016` | `year_built` | max(0, 2016-year_built) | `int16` | 0..116 | building vintage |
| `log_square_feet` | `square_feet` | log1p(square_feet) | `float32` | >=0 | compress area scale |
| `square_feet_per_floor` | `square_feet`, `floor_count` | square_feet/max(floor_count,1) | `float32` | >0 | approximate floor plate |
| `temperature_difference` | `air_temperature`, `dew_temperature` | air_temperature-dew_temperature | `float32` | observed | air moisture spread |
| `relative_humidity` | `air_temperature`, `dew_temperature` | 100*exp(17.625*Td/(243.04+Td)-17.625*T/(243.04+T)), clipped | `float32` | 0..100 | Magnus-formula humidity approximation |
| `wind_direction_sin` | `wind_direction` | sin(direction*pi/180) | `float32` | -1..1 | circular wind direction |
| `wind_direction_cos` | `wind_direction` | cos(direction*pi/180) | `float32` | -1..1 | circular wind direction |
| `is_precipitating` | `precip_depth_1_hr` | precip_depth_1_hr > 0 | `bool` | False..True | active precipitation |
| `is_freezing` | `air_temperature` | air_temperature <= 0 C | `bool` | False..True | freezing conditions |
| `is_hot` | `air_temperature` | air_temperature >= 30 C | `bool` | False..True | documented hot-weather threshold |
| `heating_degree_proxy` | `air_temperature` | max(0,18-air_temperature) | `float32` | >=0 | heating demand; 18 C balance point |
| `cooling_degree_proxy` | `air_temperature` | max(0,air_temperature-18) | `float32` | >=0 | cooling demand; 18 C balance point |
| `log_square_feet_x_air_temperature` | `square_feet`, `air_temperature` | log1p(square_feet)*air_temperature | `float32` | observed | size-temperature interaction |
| `building_age_x_air_temperature` | `year_built`, `air_temperature` | building_age_2016*air_temperature | `float32` | observed | vintage-temperature interaction |
| `heating_degree_x_log_square_feet` | `air_temperature`, `square_feet` | heating_degree_proxy*log_square_feet | `float32` | >=0 | size-adjusted heating exposure |
| `cooling_degree_x_log_square_feet` | `air_temperature`, `square_feet` | cooling_degree_proxy*log_square_feet | `float32` | >=0 | size-adjusted cooling exposure |

Relative humidity uses the Magnus approximation with constants 17.625 and 243.04 °C and is clipped to its physical 0–100% range. Heating/cooling degree proxies use a documented **18 °C balance point**. `is_hot` uses **30 °C**; `is_freezing` uses **0 °C**; precipitation means measured depth greater than zero. Building age uses the dataset year 2016 and is clipped at zero.

## Categorical Handling Decision

`primary_use`, `meter`, `site_id`, and `building_id` are retained unchanged. They should be declared categorical for category-aware tree models. Integer identifiers must not be interpreted as continuous by linear/distance-based models; encoding must occur only after time splitting and be fit on training data. `building_id`, `meter`, `site_id`, and `timestamp` remain available for grouping, auditing and splitting. High-cardinality identifiers were not dropped.

## Lag and Rolling Feature Decision

**Deferred.** The application’s prediction horizon (next hour versus arbitrary future time) and availability of historical readings at inference are not established. Implementing them now could leak current/future targets. A future experiment must group by (`building_id`, `meter`), sort chronologically, apply `shift` before every rolling calculation, define first-observation behavior, construct features separately within time-safe partitions, prove inference availability, and measure memory cost.

## Leakage Prevention and Target Preservation

The machine-readable dictionary confirms that no engineered feature lists `meter_reading` as a source. Independent row-group comparison verified the target and all 16 original columns unchanged. The clean input SHA-256 remained `251ca27b85f2063f9929f4716c71440fcf1a1a1129f2481a0fa3e9457723dc4b` before and after the run.

## Feature Validation

- Row count unchanged: **True** (20,216,100)
- Duplicate logical keys before/after: **0 / 0**
- Missing values / infinite values: **0 / 0**
- Invalid timestamps: **0**
- Original columns and target unchanged: **True / True**
- Input file unchanged: **True**
- Overall validation: **PASSED**

### Observed Engineered-Feature Ranges

| Feature | Minimum | Maximum |
| --- | ---: | ---: |
| `hour` | 0 | 23 |
| `day_of_week` | 0 | 6 |
| `day_of_month` | 1 | 31 |
| `day_of_year` | 1 | 366 |
| `week_of_year` | 1 | 53 |
| `month` | 1 | 12 |
| `quarter` | 1 | 4 |
| `is_weekend` | 0 | 1 |
| `hour_sin` | -1 | 1 |
| `hour_cos` | -1 | 1 |
| `day_of_week_sin` | -0.974928 | 0.974928 |
| `day_of_week_cos` | -0.900969 | 1 |
| `month_sin` | -1 | 1 |
| `month_cos` | -1 | 1 |
| `building_age_2016` | 0 | 116 |
| `log_square_feet` | 5.64897 | 13.682 |
| `square_feet_per_floor` | 141.5 | 875000 |
| `temperature_difference` | -1.1 | 51.7 |
| `relative_humidity` | 3.75938 | 100 |
| `wind_direction_sin` | -1 | 1 |
| `wind_direction_cos` | -1 | 1 |
| `is_precipitating` | 0 | 1 |
| `is_freezing` | 0 | 1 |
| `is_hot` | 0 | 1 |
| `heating_degree_proxy` | 0 | 46.9 |
| `cooling_degree_proxy` | 0 | 29.2 |
| `log_square_feet_x_air_temperature` | -394.961 | 642.119 |
| `building_age_x_air_temperature` | -3024 | 5144.8 |
| `heating_degree_x_log_square_feet` | 0 | 640.957 |
| `cooling_degree_x_log_square_feet` | 0 | 397.243 |

## Memory and Storage Impact

| Measure | Input | Output |
| --- | ---: | ---: |
| Logical Arrow memory | 2741.57 MB | 4295.98 MB |
| Snappy Parquet size | 147.78 MB | 313.51 MB |
| Columns | 16 | 46 |

Added columns: **30**. Processing duration: **53.91 seconds**. Bounded calendar values use `int8`/`int16`, indicators use Boolean, and engineered continuous values use `float32`.

## Remaining Modelling Risks and Baseline Recommendation

IDs require model-appropriate encoding after chronological splitting; imputed metadata/weather uncertainty remains; interaction magnitudes and collinearity may affect linear models; site/building generalization must be evaluated; and target skew/outliers remain intentionally untouched. For baselines, start with calendar/cyclical variables, original weather, degree proxies, log area, building age, floor-adjusted area, meter and primary use using training-only categorical handling. Interaction features can be ablated.

## Readiness for Task 2.4

The feature dataset is validated and ready for a separate time-based splitting task. Task 2.3 stops here; no split, encoding fit, scaling or model training has occurred.
