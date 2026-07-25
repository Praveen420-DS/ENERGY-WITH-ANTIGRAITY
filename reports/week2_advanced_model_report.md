# Week 2 Task 2.5 — Advanced Model Training and Comparison

## Objective and audited baseline contract

XGBoost, LightGBM, and CatBoost were compared with the exact Task 2.4 target, 42 predictors,
exclusions, seed, chronological boundaries, and metric definitions. Baseline artifacts were read only.
The validated input has 20,216,100 rows × 46 columns and remained unchanged.

## Hardware and libraries

- CPU: 8 logical cores; training threads: 6
- RAM: 15.69 GiB
- GPU: not verified; all training used CPU
- XGBoost 3.2.0, LightGBM 4.6.0, CatBoost 1.2.8

## Exact chronological split

Training ends 2016-08-31 23:00:00 (13,358,457 rows), validation covers
September–October (3,441,800), and test covers November–December
(3,415,843). There is no shuffle or overlap. Mapping, preprocessing, and fitting
use training rows only. Test predictions were made only after each family configuration was frozen.

## Target drift

| Split | Mean | Median | Std | Maximum | Extreme share |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 2885.96 | 77.00 | 186006.69 | 21904700.00 | 0.1002% |
| validation | 550.58 | 85.00 | 8813.01 | 880374.00 | 0.0885% |
| test | 688.83 | 79.12 | 59822.56 | 21847900.00 | 0.1139% |

The large validation/test RMSE gap is driven by target-distribution drift and a very small extreme-value
tail. Decile and high-consumption errors in the JSON quantify how extreme rows dominate squared error.
No outlier was removed.

## Target and categorical strategies

Raw target and `log1p(meter_reading)` were screened separately. Log predictions use `expm1`; only negative
inverse predictions are clipped to zero, with the pre-clip rate reported. Selection uses validation only.
The stored target is unchanged.

The baseline predictor contract excludes `building_id`, `site_id`, and raw `timestamp`; `meter` and
`primary_use` are categorical. XGBoost uses training-fitted ordinal codes, LightGBM uses training-defined
pandas categorical levels, and CatBoost uses native string categoricals. No target encoding is used.

## Controlled experiment design

Six screening fits use 2,000,000 evenly spaced, row-order-preserving
training rows and 500,000 evenly spaced validation rows.
This preserves the full chronological span and categorical coverage. The better target strategy per family
is then refitted on all 13,358,457 training rows with histogram/native CPU methods and
early stopping. This is bounded tuning, not a grid search.

| ID | Model | Target | Train rows | Val RMSE | Val MAE | Val R² | RMSLE | Train sec | Infer sec |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| xgboost_raw_screen | xgboost | raw | 2,000,000 | 9226.68 | 712.07 | 0.0207 | 2.8876 | 10.6 | 0.13 |
| xgboost_log_screen | xgboost | log | 2,000,000 | 9248.53 | 404.63 | 0.0161 | 1.3402 | 35.2 | 0.61 |
| lightgbm_raw_screen | lightgbm | raw | 2,000,000 | 9368.42 | 1509.51 | -0.0096 | 3.7000 | 5.1 | 0.13 |
| lightgbm_log_screen | lightgbm | log | 2,000,000 | 9256.42 | 416.61 | 0.0144 | 1.3885 | 24.5 | 1.46 |
| catboost_raw_screen | catboost | raw | 2,000,000 | 9321.20 | 1215.67 | 0.0005 | 3.4792 | 43.0 | 0.41 |
| catboost_log_screen | catboost | log | 2,000,000 | 9286.06 | 449.18 | 0.0081 | 1.4927 | 192.8 | 0.47 |

## Final comparison, including Task 2.4 baselines

| Model | Target | Coverage | Val RMSE | Val MAE | Val R² | Test RMSE | Test MAE | Test R² | Train sec | Test infer sec | Bytes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| linear_regression | raw | full | 13488.75 | 7962.93 | -1.3426 | 60550.04 | 8051.82 | -0.0245 | 22.4 | 0.21 | 3,919 |
| decision_tree | raw | full | 8768.78 | 391.24 | 0.0100 | 59798.41 | 484.42 | 0.0008 | 385.0 | 0.45 | 933,751 |
| random_forest | raw | full | 8766.30 | 365.49 | 0.0106 | 59372.42 | 518.00 | 0.0150 | 1631.9 | 1.92 | 27,321,439 |
| xgboost | raw | full | 8731.46 | 702.07 | 0.0184 | 59926.47 | 1024.74 | -0.0035 | 70.4 | 0.81 | 1,779,459 |
| lightgbm | log | full | 8730.62 | 382.79 | 0.0186 | 59794.52 | 527.71 | 0.0009 | 243.8 | 23.16 | 2,755,875 |
| catboost | log | full | 8754.26 | 408.79 | 0.0133 | 59791.50 | 533.94 | 0.0010 | 2280.6 | 3.40 | 1,956,394 |

## Subgroups, errors, and interpretability

Machine-readable meter, site, primary-use, zero/nonzero, building, target-decile, and high-consumption
metrics are in the metrics JSON for every advanced finalist. Feature plots use native gain for XGBoost and
LightGBM, and prediction-values-change for CatBoost. Gain can overemphasize flexible predictors and native
importance is associative, not causal. SHAP was not run because it was not installed and native importance
was sufficient for this memory-constrained comparison.

## Selection

- Best validation model: **lightgbm**
- Best test model (descriptive only): **catboost**
- Fastest advanced model: **xgboost**
- Smallest advanced artifact: **xgboost**
- Recommended Task 2.6 candidate: **random_forest**
- Selected target strategy: **raw**

The recommendation follows validation RMSE/MAE first, then test stability, subgroup behavior, inference,
size, compatibility, and reproducibility. Test results did not drive selection.

## Limitations and recommendations

Only one year is available; late-period extremes and temporal drift remain; identifier exclusion limits
building-specific memorization; categorical behavior for unseen values needs monitoring; and native feature
importance is not causal. Task 2.6 should package—but not retrain—the selected candidate, retain category
mappings, and define input validation. Later robustness work should use rolling-origin evaluation, robust
losses, calibration for extremes, and carefully defined time-safe lag features.

All artifacts reload, deterministic smoke predictions match, counts and metrics agree, and input/baseline
fingerprints are unchanged. Task 2.5 is **100% complete**.
