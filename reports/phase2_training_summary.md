# Phase 2 Electricity Model Comparison

Candidates only; production v1.0.0 was not changed. Training used a deterministic bounded subset of 249,766 training-period rows because the requested in-memory estimators cannot safely consume the entire multi-million-row training partition on this workstation. Validation and test metrics use their complete chronological partitions.

| Model | Val MAE | Val RMSE | Val R2 | Val RMSLE | Test MAE | Test RMSE | Test R2 | Test RMSLE | Train sec | MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dummy | 157.8455 | 396.1904 | -0.107701 | 1.625886 | 151.3031 | 430.7501 | -0.079860 | 1.549897 | 0.00 | 0.00 |
| linear_regression | 128.0886 | 286.9154 | 0.419072 | 1.652214 | 136.5844 | 328.0243 | 0.373777 | 1.620558 | 0.74 | 0.00 |
| ridge | 128.8791 | 286.9955 | 0.418747 | 1.647019 | 138.8706 | 328.5240 | 0.371868 | 1.615574 | 0.09 | 0.00 |
| random_forest | 45.0380 | 178.7213 | 0.774593 | 0.851919 | 57.8926 | 302.3691 | 0.467902 | 0.808035 | 74.39 | 21.13 |
| hist_gradient_boosting | 77.0613 | 192.1524 | 0.739441 | 1.111522 | 85.8720 | 301.4893 | 0.470994 | 1.030760 | 5.62 | 0.24 |

Best candidate: **random_forest**, selected by validation MAE, RMSLE, then R2. Consumption bands use training-target percentiles: small <= 59.6300, medium <= 402.5400, large <= 1645.8120, and peak above that. The electricity unit remains unverified.

XGBoost status: **skipped** — No module named 'xgboost'.

## Recommendation

Treat the winner as a v2 candidate only. Review drift, band errors, residual plots, and training-cap sensitivity before any packaging or production decision.
