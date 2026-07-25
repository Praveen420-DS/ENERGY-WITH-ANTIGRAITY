# Week 1 Dataset Understanding Report

## Executive Summary

The three files form a coherent supervised regression dataset for hourly building energy prediction. `meter_reading` is the non-negative target. Training observations join many-to-one to building metadata through `building_id`; metadata supplies `site_id`; weather then joins many-to-one on (`site_id`, `timestamp`). The source files are suitable for model development, subject to careful missing-value handling, outlier-robust target treatment, categorical encoding, and leakage-safe time splitting.

## Dataset Overview

| Dataset | Rows | Columns | CSV size (MB) |
| --- | --- | --- | --- |
| train.csv | 20,216,100 | 4 | 647.18 |
| building_metadata.csv | 1,449 | 6 | 0.04 |
| weather_train.csv | 139,773 | 9 | 7.1 |

- Time coverage: **2016-01-01 00:00:00 through 2016-12-31 23:00:00** (8,784 expected hourly positions).
- Buildings: **1,449** across **16** sites.
- Target: `train.csv.meter_reading`; mean **2117.121**, sampled median **79.280**, maximum **21,904,700.000**.
- Feature roles: IDs/categorical (`building_id`, `site_id`, `meter`, `primary_use`); static numeric (`square_feet`, `year_built`, `floor_count`); time (`timestamp`); weather (temperature, dew point, pressure, wind, cloud and precipitation fields).

## Relationship Validation

| Step | Left key | Right key | Cardinality / result |
| --- | --- | --- | --- |
| 1 | `train.building_id` | `building_metadata.building_id` | many-to-one; metadata key unique: **True**; unmatched IDs: **0** |
| 2 | (`site_id`, `timestamp`) after step 1 | `weather_train` (`site_id`, `timestamp`) | many-to-one; weather duplicate keys: **0** |
| Final | retain all training rows | left joins in the order above | exact weather-key match: **99.55%**; unmatched rows: **90,495** |

The required merge order is train → building metadata → weather. Joining weather before metadata is impossible because train has no `site_id`. Use left joins so target rows are never silently discarded, and assert `validate='many_to_one'` at both stages. Train key (`building_id`, `meter`, `timestamp`) duplicate count is **0**. Sites referenced by train but absent from weather: **0**.

## Column Inventory and Unique Values

| Dataset | Column | Inferred type | Unique / role |
| --- | --- | --- | --- |
| Train | `building_id` | integer | 1,449; categorical identifier / merge key |
| Train | `meter` | integer | 4; categorical meter type |
| Train | `timestamp` | datetime after parsing | hourly time key across 8,784 hours |
| Train | `meter_reading` | float | continuous non-negative prediction target |
| Metadata | `site_id` | integer | 16; categorical/site merge key |
| Metadata | `building_id` | integer | 1,449; unique primary key |
| Metadata | `primary_use` | string | 16; categorical use class |
| Metadata | `square_feet` | integer | static numeric building area |
| Metadata | `year_built`, `floor_count` | float | nullable static numeric fields |
| Weather | `site_id`, `timestamp` | integer, datetime | composite unique key |
| Weather | remaining 7 columns | float | continuous/ordinal weather measurements |

## Data Types and Semantics

CSV inference yields integer IDs/codes, floating-point target/weather values, text timestamps, and text `primary_use`. Parse timestamps explicitly. Treat identifier numbers and `meter` as categorical—not continuous measurements. `year_built` and `floor_count` are nullable numeric metadata. No raw column is constant.

## ML Problem Definition

- Problem: supervised tabular time-aware regression at building–meter–hour granularity.
- Expected output: one non-negative consumption estimate per requested building, meter and timestamp.
- Recommended primary metric: RMSLE, matching a highly right-skewed non-negative target and reducing domination by extreme loads. Also report MAE and RMSE; consider meter/site-stratified metrics.
- Baselines for Week 2 evaluation: global/median, per-meter median, linear/Ridge, decision tree, Random Forest or HistGradientBoosting.
- Advanced candidates (later): LightGBM, XGBoost, CatBoost, and carefully validated temporal/ensemble approaches.
- Leakage risks: random row splits, future-derived rolling aggregates, target encodings fit outside a training fold, and statistics computed using validation/test periods.

## Suitability Assessment

The data are suitable and sufficient for an initial end-to-end prediction model: they contain a clear target, a full year of hourly observations, static building context, multiple utility meters, site identifiers, and contemporaneous weather. Advantages are scale, heterogeneous buildings, seasonality, and realistic missingness. Limitations include a single-year window, anonymized sites, incomplete metadata/weather, extreme target skew, zeros, possible meter-specific units/behavior, and lack of occupancy, tariffs, holidays, equipment and operational schedules. No additional dataset is required to begin modelling. Optional calendars/holidays or occupancy/context data could improve later performance, but must be provenance-checked and time-valid.
