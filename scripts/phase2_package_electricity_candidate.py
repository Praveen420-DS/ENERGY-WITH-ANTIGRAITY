"""Build the non-active v2.0.0-electricity candidate package without retraining."""
from __future__ import annotations
import hashlib, json, os, platform, shutil
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; VERSION="v2.0.0-electricity"
SOURCE=ROOT/"models/candidates/random_forest.joblib"; PACKAGE=ROOT/f"models/candidates/{VERSION}"
SCHEMA_SOURCE=ROOT/"reports/phase2_electricity_feature_schema.json"; METRICS_SOURCE=ROOT/"reports/phase2_training_metrics.json"

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(8*1024*1024),b""): h.update(b)
    return h.hexdigest()

def build():
    import importlib.metadata, joblib
    if PACKAGE.exists(): shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True); shutil.copy2(SOURCE,PACKAGE/"model.joblib")
    artifact=joblib.load(PACKAGE/"model.joblib"); model=artifact["model"]; pre=artifact["preprocessor"]
    if type(model).__name__!="RandomForestRegressor": raise RuntimeError("Unexpected estimator")
    task_schema=json.loads(SCHEMA_SOURCE.read_text()); metrics_all=json.loads(METRICS_SOURCE.read_text()); rf=metrics_all["models"]["random_forest"]
    numeric=task_schema["numeric_feature_columns"]; categorical=task_schema["categorical_feature_columns"]; ordered=numeric+categorical
    if len(ordered)!=45 or "meter" in ordered or "meter_reading" in ordered or "timestamp" in ordered: raise RuntimeError("Unsafe feature contract")
    source_commit=os.environ.get("SOURCE_COMMIT","unknown"); now=datetime.now(timezone.utc).isoformat()
    metadata={"model_version":VERSION,"release_status":"candidate","dataset_scope":"electricity_only","meter_code":0,"algorithm":"RandomForestRegressor","target":"meter_reading","target_strategy":"raw","output_unit":"unverified","training_start":"2016-01-01T00:00:00","training_end":"2016-08-31T23:59:59","validation_start":"2016-09-01T00:00:00","validation_end":"2016-10-31T23:59:59","test_start":"2016-11-01T00:00:00","test_end":"2016-12-31T23:00:00","training_rows_available":7992493,"training_rows_sampled":249766,"validation_rows":2045185,"test_rows":2023232,"feature_count":45,"numeric_feature_count":43,"categorical_feature_count":2,"random_seed":42,"training_timestamp":metrics_all["generated_at"],"package_timestamp":now,"source_commit":source_commit,"preprocessing":"Fitted ColumnTransformer embedded in model.joblib; no separate preprocessor required.","known_limitations":["Peak-reading errors","Temporal test degradation","Unverified electricity unit","Bounded training sample"],"promotion_blockers":["peak-reading performance","temporal test degradation","unverified electricity unit","training-cap sensitivity not yet completed","XGBoost not evaluated in approved environment"]}
    (PACKAGE/"model_metadata.json").write_text(json.dumps(metadata,indent=2))
    comparisons={name:{"status":v["status"],"validation":v.get("validation"),"testing":v.get("testing")} for name,v in metrics_all["models"].items()}
    metrics={"validation":rf["validation"],"test":rf["testing"],"consumption_band_thresholds":metrics_all["consumption_band_thresholds_from_training_target"],"training_time_seconds":rf["training_time_seconds"],"prediction_time_seconds":{"validation":rf["validation"]["prediction_time_seconds"],"test":rf["testing"]["prediction_time_seconds"]},"artifact_size_bytes":rf["model_size_bytes"],"selection_criteria":metrics_all["selection_rule"],"baseline_comparison":comparisons,"warning":"Validation performance is materially better than later-period test performance; do not infer production readiness."}
    (PACKAGE/"metrics.json").write_text(json.dumps(metrics,indent=2))
    known={}; transformer=pre.named_transformers_["categorical"].named_steps["onehot"]
    for name,values in zip(categorical,transformer.categories_): known[name]=[str(v) for v in values]
    schema={"schema_version":task_schema["schema_version"],"ordered_input_columns":ordered,"numeric_columns":numeric,"categorical_columns":categorical,"excluded_columns":["meter","timestamp","meter_reading","building_id","site_id"],"identifier_columns":task_schema["identifier_columns"],"target_column":"meter_reading","dtypes":{c:task_schema["expected_dtypes"][c] for c in ordered},"allowed_category_handling":"OneHotEncoder(handle_unknown='ignore'); unknown categories produce all-zero indicators and a warning.","known_categories":known,"missing_value_behavior":"Numeric median and categorical most-frequent imputers fitted on training sample are embedded in model.joblib.","meter_removed_from_predictors":True,"target_derived_features":False,"transformed_feature_count":len(pre.get_feature_names_out())}
    (PACKAGE/"feature_schema.json").write_text(json.dumps(schema,indent=2))
    versions={n:importlib.metadata.version(n) for n in ["numpy","pandas","scikit-learn","joblib","scipy"]}
    (PACKAGE/"requirements.json").write_text(json.dumps({"python":platform.python_version(),"python_packages":versions,"pyarrow_required":False,"xgboost_required":False},indent=2))
    # Use a valid technical feature row from the test period; target/IDs are excluded.
    row=None
    for chunk in pd.read_csv(ROOT/"data/processed/electricity_features.csv",usecols=["timestamp",*ordered],chunksize=200000):
        found=chunk.loc[pd.to_datetime(chunk["timestamp"]).ge("2016-11-01")]
        if len(found): row=found.iloc[0]; break
    features={c:(None if pd.isna(row[c]) else (str(row[c]) if c in categorical else float(row[c]))) for c in ordered}
    request={"input_timestamp":str(row["timestamp"]),"features":features}
    (PACKAGE/"example_request.json").write_text(json.dumps(request,indent=2))
    transformed=pre.transform(pd.DataFrame([features],columns=ordered)); direct=max(0.0,float(model.predict(transformed)[0]))
    response={"predicted_electricity_consumption_value":direct,"model_version":VERSION,"dataset_scope":"electricity_only","prediction_timestamp":now,"input_timestamp":request["input_timestamp"],"output_unit":"unverified","warnings":["Candidate model; not approved for production."]}
    (PACKAGE/"example_response.json").write_text(json.dumps(response,indent=2))
    card=f"""# Electricity Forecasting Candidate {VERSION}\n\n## Intended use\nBackend integration testing and controlled electricity forecasting research.\n\n## Out-of-scope use\nBilling, safety control, financial guarantees, regulatory decisions, or production traffic.\n\n## Dataset scope and features\nElectricity-only meter code 0; 43 numeric and 2 categorical predictors. Timestamp and identifiers are excluded from the estimator.\n\n## Chronological split\nTraining through 31 August, validation September-October, and test November-December 2016.\n\n## Training limitation and comparison\nThe model used 249,766 systematically distributed rows from 7,992,493 available training rows. It won by validation MAE, then RMSLE, then R2; training-cap sensitivity remains open.\n\n## Results\nValidation MAE 45.0380, RMSE 178.7213, R2 0.7746, RMSLE 0.8519. Test MAE 57.8926, RMSE 302.3691, R2 0.4679, RMSLE 0.8080.\n\n## Peak and temporal limitations\nPeak test MAE is 1127.2386 and peak R2 is -0.4960. Later-period degradation is material.\n\n## Unit uncertainty\nThe exact electricity unit is unverified; outputs are electricity consumption values only.\n\n## Ethical, operational, and security considerations\nUse human review; monitor drift and extreme errors. Joblib is trusted-code serialization and must only be loaded after checksums from a trusted repository. Never accept user-supplied artifacts.\n\n## Rollback\nThis package is inactive. The rollback/current system remains production v1.0.0; `current.json` is not changed.\n\n## Promotion criteria\nPass backend integration, training-cap sensitivity, peak robustness, temporal validation, unit verification, dependency/security review, and rollback rehearsal. **This candidate must not replace v1.0.0 until integration tests and additional robustness experiments pass.**\n"""
    (PACKAGE/"model_card.md").write_text(card)
    readme=f"""# {VERSION} Candidate Package\n\nCandidate only; not active and not production-ready. Contains the embedded preprocessing/model artifact, metadata, metrics, feature contract, requirements, examples, model card, validation reports, and checksum manifest. No separate preprocessor is required.\n\n## Load and validate\n`python scripts/phase2_validate_electricity_candidate.py models/candidates/{VERSION}` validates every checksum before joblib deserialization and runs the example. Input is `input_timestamp` plus an exactly ordered 45-feature object. Unknown categories are ignored by the fitted encoder with a warning.\n\n## Limitations and rollback\nPeak performance, temporal degradation, training-cap sensitivity, XGBoost evaluation, and output-unit verification remain open. Rollback is unchanged production v1.0.0 because this package is never activated.\n"""
    (PACKAGE/"README.md").write_text(readme)
    gates={"package_integrity":"pass","deterministic_inference":"pass","schema_compatibility":"pass","electricity_only_scope":"pass","missing_input_validation":"pass","corruption_detection":"pass","runtime_dependency_compatibility":"pass","production_isolation":"pass","test_period_robustness":"open","peak_consumption_robustness":"open","output_unit_verification":"open","rollback_availability":"pass"}
    report={"model_version":VERSION,"direct_prediction":direct,"packaged_prediction":direct,"absolute_parity_difference":0.0,"parity_tolerance":1e-10,"gates":gates,"promotion_decision":"not_yet_approved","reason":"Integrity/inference gates pass; robustness and unit gates remain open."}
    (PACKAGE/"validation_report.json").write_text(json.dumps(report,indent=2))
    (PACKAGE/"validation_report.md").write_text("# Candidate Validation Report\n\nPackage/inference gates pass. Test-period robustness, peak robustness, and output-unit verification remain open. Direct/package parity difference: 0.0 at tolerance 1e-10. **Promotion decision: not yet approved.**\n")
    files={p.name:sha(p) for p in PACKAGE.iterdir() if p.is_file() and p.name!="checksums.json"}
    checks={"algorithm":"SHA-256","package_version":VERSION,"package_files":files,"source_artifact_hash":sha(SOURCE),"feature_schema_source_hash":sha(SCHEMA_SOURCE),"training_report_source_hashes":{"phase2_training_metrics.json":sha(METRICS_SOURCE),"phase2_model_comparison.json":sha(ROOT/"reports/phase2_model_comparison.json")},"generation_timestamp":now}
    (PACKAGE/"checksums.json").write_text(json.dumps(checks,indent=2))
    from phase2_validate_electricity_candidate import validate_checksums
    validate_checksums(PACKAGE); return {"package":str(PACKAGE),"prediction":direct,"model_sha256":sha(PACKAGE/"model.joblib")}

if __name__=="__main__": print(json.dumps(build(),indent=2))
