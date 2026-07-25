# Week 1 Completion Summary

## Executive Summary

Week 1 is complete. All three source datasets were profiled, their relationships and keys were validated, the prediction problem was defined, data-quality risks were documented, and reproducible EDA figures were generated. No model, feature engineering, preprocessing pipeline, processed dataset, or application/infrastructure change was created.

## Key Findings

- The prescribed left-merge chain is `train` → metadata on `building_id` → weather on (`site_id`, `timestamp`).
- The target is `meter_reading`; it is non-negative, **9.27%** zero, and extremely right-skewed (sample skew **94.60**).
- Coverage spans **2016-01-01 00:00:00 to 2016-12-31 23:00:00**, enabling a chronological holdout.
- Dataset suitability: **suitable and sufficient for initial modelling**, with no mandatory extra dataset.
- Main risks: missing weather/metadata, extreme meter-specific outliers, zeros, high-cardinality IDs, site/meter heterogeneity, memory pressure, and temporal leakage.

## Week 2 Plan (Do Not Implement in Week 1)

1. Establish chronological train/validation/test windows (for example, early months for training, a subsequent month for validation, and the latest 1–2 months as untouched test); add rolling-origin validation if compute permits.
2. Implement training-only missing-value rules and missingness indicators; compare site/time interpolation for weather with robust median strategies.
3. Engineer calendar/seasonality features, building age, weather interactions and strictly lagged/rolling consumption features. Every target-derived feature must use past data only.
4. Encode `primary_use`, `meter`, `site_id` and high-cardinality `building_id` using model-appropriate, fold-safe methods. Avoid leakage-prone global target encoding.
5. Scale only for models that require it; fit scalers on training data only. Evaluate `log1p(meter_reading)` for skew.
6. Compare naive medians and linear/tree baselines before boosted-tree candidates; report RMSLE, MAE and RMSE overall and by meter/site.

## Completion Status

- Week 1 completion: **100%**
- Official status: **Complete**
- Week 2 readiness: **Ready**, subject to preserving the documented time-based validation and leakage controls.
