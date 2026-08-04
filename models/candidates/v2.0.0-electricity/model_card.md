# Electricity Forecasting Candidate v2.0.0-electricity

## Intended use
Backend integration testing and controlled electricity forecasting research.

## Out-of-scope use
Billing, safety control, financial guarantees, regulatory decisions, or production traffic.

## Dataset scope and features
Electricity-only meter code 0; 43 numeric and 2 categorical predictors. Timestamp and identifiers are excluded from the estimator.

## Chronological split
Training through 31 August, validation September-October, and test November-December 2016.

## Training limitation and comparison
The model used 249,766 systematically distributed rows from 7,992,493 available training rows. It won by validation MAE, then RMSLE, then R2; training-cap sensitivity remains open.

## Results
Validation MAE 45.0380, RMSE 178.7213, R2 0.7746, RMSLE 0.8519. Test MAE 57.8926, RMSE 302.3691, R2 0.4679, RMSLE 0.8080.

## Peak and temporal limitations
Peak test MAE is 1127.2386 and peak R2 is -0.4960. Later-period degradation is material.

## Unit uncertainty
The exact electricity unit is unverified; outputs are electricity consumption values only.

## Ethical, operational, and security considerations
Use human review; monitor drift and extreme errors. Joblib is trusted-code serialization and must only be loaded after checksums from a trusted repository. Never accept user-supplied artifacts.

## Rollback
This package is inactive. The rollback/current system remains production v1.0.0; `current.json` is not changed.

## Promotion criteria
Pass backend integration, training-cap sensitivity, peak robustness, temporal validation, unit verification, dependency/security review, and rollback rehearsal. **This candidate must not replace v1.0.0 until integration tests and additional robustness experiments pass.**
