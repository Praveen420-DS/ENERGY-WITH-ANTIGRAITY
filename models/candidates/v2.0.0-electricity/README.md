# v2.0.0-electricity Candidate Package

Candidate only; not active and not production-ready. Contains the embedded preprocessing/model artifact, metadata, metrics, feature contract, requirements, examples, model card, validation reports, and checksum manifest. No separate preprocessor is required.

## Load and validate
`python scripts/phase2_validate_electricity_candidate.py models/candidates/v2.0.0-electricity` validates every checksum before joblib deserialization and runs the example. Input is `input_timestamp` plus an exactly ordered 45-feature object. Unknown categories are ignored by the fitted encoder with a warning.

## Limitations and rollback
Peak performance, temporal degradation, training-cap sensitivity, XGBoost evaluation, and output-unit verification remain open. Rollback is unchanged production v1.0.0 because this package is never activated.
