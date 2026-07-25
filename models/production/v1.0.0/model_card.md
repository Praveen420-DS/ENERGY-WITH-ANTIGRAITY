# Energy Consumption Random Forest — v1.0.0

## Overview

This package predicts energy `meter_reading` values from building, meter, timestamp, and weather inputs.
It contains the frozen Task 2.4 Random Forest pipeline, including preprocessing and categorical encoding.
Meter units vary by meter type and must be interpreted using the application's meter metadata.

## Intended use

Use for non-critical forecasting support and Week 3 API integration after request validation. Supported
inputs follow `feature_schema.json`; the package internally reproduces the exact Task 2.3 features.

Do not use this model for billing, safety-critical control, regulatory decisions, guaranteed financial
savings, or autonomous equipment control without substantial additional validation.

## Training and evaluation

- Source: `data/processed/feature_dataset.parquet`, 20,216,100 observations
- Training: 13,358,457 chronological rows through 2016-08-31
- Validation: 3,441,800 rows during September–October 2016
- Test: 3,415,843 rows during November–December 2016
- Validation: RMSE 8766.30, MAE 365.49, R² 0.0106
- Test: RMSE 59372.42, MAE 518.00, R² 0.0150

## Input and output

All 15 raw fields are required. Missing, non-finite, incorrectly typed, or out-of-contract inputs are
rejected; inference does not silently impute API omissions. Unknown `primary_use` values are accepted with
a warning because the fitted encoder uses `handle_unknown="ignore"`. Building and site IDs are required
for traceability but excluded from prediction, so unseen values are accepted with warnings. Meter must be
0–3. Output is clipped at zero if the raw regressor returns a negative value.

## Limitations and risks

Performance is weak on extreme target values and test-period drift is substantial. R² is low, rare extreme
readings dominate RMSE, units differ by meter, and the model was evaluated on only one calendar year.
Training data contains pre-imputed values, but the production contract does not accept missing inputs.
Unknown categories receive no learned category effect. Predictions may be unreliable for new geographies,
buildings, future periods, distribution shifts, or operational regimes absent from training.

## Ethical and operational considerations

Monitor errors by meter, site, building, primary use, time, and target magnitude. Log validation warnings,
latency, clipping frequency, and drift without storing unnecessary sensitive information. Human review is
required for consequential decisions.

## Monitoring and retraining

Monitor input ranges, unknown-category rates, residual drift, extreme-event errors, latency, and failed
requests. Reassess at least quarterly or after material building/weather changes. Retrain only through a
versioned, chronological evaluation process; investigate robust losses and rolling-origin validation first.
