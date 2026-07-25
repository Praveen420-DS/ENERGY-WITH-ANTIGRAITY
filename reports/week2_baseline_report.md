# Week 2 Task 2.4 — Baseline Model Report

## Dataset summary

The validated Task 2.3 dataset contains **20,216,100 rows × 46 columns**
from 2016-01-01 00:00:00 through 2016-12-31 23:00:00. It has no missing
values, invalid timestamps, or duplicate (`building_id`, `meter`, `timestamp`) keys. The target is
`meter_reading`; **42 predictors** are used.

### Excluded columns

- `timestamp`: Used only to define chronological partitions; raw epoch magnitude is not a predictor.
- `building_id`: High-cardinality identity could encourage memorization and is not portable to unseen buildings.
- `site_id`: Site identity could proxy geography/collection artifacts; weather and building attributes are retained.

## Chronological split and leakage prevention

| Split | Start | End | Rows | Share |
| --- | --- | --- | ---: | ---: |
| Train | 2016-01-01 00:00:00 | 2016-08-31 23:00:00 | 13,358,457 | 66.08% |
| Validation | 2016-09-01 00:00:00 | 2016-10-31 23:00:00 | 3,441,800 | 17.03% |
| Test | 2016-11-01 00:00:00 | 2016-12-31 23:00:00 | 3,415,843 | 16.90% |

Rows are split by timestamp without shuffling. The validation and test periods occur strictly after training.
The preprocessing transformer is fitted on training rows only; validation/test rows are transform-only.
No target-derived feature is present, and target values never enter preprocessing.

## Preprocessing

Numeric predictors receive training-only median imputation and standardization, required for stable linear
coefficients. `primary_use` and `meter` receive training-only most-frequent imputation and one-hot encoding
with unknown categories ignored. The same fitted transformer is shared by all models for a controlled
comparison. Scaling is mathematically unnecessary for trees but does not change their split ordering.

## Baseline models

- Linear Regression: unregularized additive reference model.
- Decision Tree Regressor: nonlinear single-tree reference (`max_depth=16`, `min_samples_leaf=20`).
- Random Forest Regressor: 30-tree bagged reference (`max_depth=16`, `min_samples_leaf=20`).

No XGBoost, LightGBM, CatBoost, deployment, tuning, sampling, or observation removal was performed.

## Evaluation

| Model | Val RMSE | Val MAE | Val R² | Test RMSE | Test MAE | Test R² | Train sec | Test inference sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Linear Regression | 13488.7478 | 7962.9317 | -1.3426 | 60550.0419 | 8051.8183 | -0.0245 | 22.41 | 0.21 |
| Decision Tree | 8768.7798 | 391.2433 | 0.0100 | 59798.4087 | 484.4173 | 0.0008 | 384.99 | 0.45 |
| Random Forest | 8766.2959 | 365.4912 | 0.0106 | 59372.4199 | 518.0020 | 0.0150 | 1631.94 | 1.92 |

The best baseline by validation RMSE is **Random Forest**.
Timing is wall-clock time on the recorded execution environment and should be compared directionally.

## Feature analysis

- **Linear Regression**: `numeric__log_square_feet_x_air_temperature` (2.026e+05), `numeric__heating_degree_x_log_square_feet` (1.307e+05), `numeric__cooling_degree_x_log_square_feet` (-1.152e+05), `numeric__year_built` (-4.968e+04), `numeric__building_age_2016` (-4.872e+04)
- **Decision Tree**: `numeric__month_sin` (0.2312), `categorical__meter_2` (0.2048), `numeric__log_square_feet` (0.2046), `numeric__building_age_x_air_temperature` (0.1578), `numeric__day_of_year` (0.07691)
- **Random Forest**: `numeric__month_sin` (0.2214), `numeric__square_feet` (0.1285), `categorical__meter_2` (0.1141), `categorical__meter_0` (0.1018), `numeric__day_of_year` (0.09791)

Plots are stored under `reports/figures/baseline/`. Linear coefficients refer to standardized numeric
features and one-hot indicators; their magnitudes are comparable, but correlation among engineered features
can make individual signs and magnitudes unstable. Tree importances are impurity based and may favor
continuous/high-cardinality predictors.

## Strengths

- Fully chronological, deterministic evaluation on every observation.
- Training-only fitted preprocessing embedded with each saved model.
- Linear and nonlinear references with reload and repeat-prediction verification.

## Weaknesses and remaining risks

- A single calendar holdout does not quantify seasonal variability across years.
- Building/site IDs are excluded, so building-specific behavior is deliberately not memorized.
- Extreme target values can dominate RMSE and unregularized linear regression.
- Weather/building collinearity affects coefficient interpretation.
- Impurity importance is not causal and can be biased.
- Runtime and forest size are constrained to a practical baseline, not extensively tuned.

## Recommendations

Compare later advanced models against validation RMSE and test metrics here; add rolling-origin validation,
group-aware unseen-building evaluation, permutation importance, residual diagnostics, and carefully
time-safe lag features only after the inference horizon is defined. Advanced boosting belongs to a later task.

## Validation

Input SHA-256 before/after: `c96c89e9e3ca82892ab86c46906ce9d167eacea92ff512a359590fe4f571572b` / `c96c89e9e3ca82892ab86c46906ce9d167eacea92ff512a359590fe4f571572b`.
Models reloaded successfully, repeat predictions matched, feature counts are consistent, split ordering is
strict, and the source dataset was unchanged. **Task 2.4: 100% complete.**
