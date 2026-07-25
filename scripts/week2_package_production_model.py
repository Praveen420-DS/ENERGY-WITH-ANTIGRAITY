"""Package the frozen Task 2.4 Random Forest as a validated production version."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
import sklearn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_MODEL = ROOT / "models/baseline/random_forest.joblib"
OUTPUT_ROOT = ROOT / "models/production"
BASELINE_METRICS = ROOT / "reports/week2_baseline_metrics.json"
ADVANCED_METRICS = ROOT / "reports/week2_advanced_metrics.json"
DATASET = ROOT / "data/processed/feature_dataset.parquet"
LOG_PATH = ROOT / "reports/week2_production_packaging.log"
VERSION = "v1.0.0"
SCHEMA_VERSION = "1.0.0"
FEATURE_PIPELINE_VERSION = "week2-task2.3"
RAW_FIELDS = [
    "building_id", "meter", "timestamp", "site_id", "primary_use",
    "square_feet", "year_built", "floor_count", "air_temperature",
    "cloud_coverage", "dew_temperature", "precip_depth_1_hr",
    "sea_level_pressure", "wind_direction", "wind_speed",
]


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-model", type=Path, default=SOURCE_MODEL)
    p.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    p.add_argument("--version", default=VERSION)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--metrics", type=Path, default=BASELINE_METRICS)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-new-version", action="store_true",
                   help="Choose the next available patch version; never overwrites.")
    return p.parse_args()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def fingerprint(path: Path) -> dict:
    s = path.stat()
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path),
            "size_bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def atomic_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temp, path)


def resolve_version(output: Path, requested: str, force_new: bool) -> str:
    target = output / requested
    if not target.exists(): return requested
    if not force_new:
        raise FileExistsError(f"Production version already exists: {target}")
    prefix, _, patch = requested.rpartition(".")
    if not patch.isdigit():
        raise ValueError("--force-new-version requires a semantic version ending in an integer.")
    candidate = int(patch) + 1
    while (output / f"{prefix}.{candidate}").exists(): candidate += 1
    return f"{prefix}.{candidate}"


def input_schema(known_uses: list[str]) -> dict:
    fields = [
        ("building_id", "integer", ">= 0", 0, "Required for traceability; excluded from predictors."),
        ("meter", "integer", "one of 0,1,2,3", 0, "Rejected if outside fitted meter codes."),
        ("timestamp", "ISO-8601 string", "timezone-naive; year 1900..2100", "2016-07-15T14:00:00", "Invalid/ambiguous timestamps rejected."),
        ("site_id", "integer", ">= 0", 0, "Required for traceability; excluded from predictors."),
        ("primary_use", "string", "non-empty", "Education", "Unknown values accepted with warning and all-zero one-hot encoding."),
        ("square_feet", "number", ">= 0", 7432, "Invalid values rejected; no median fallback."),
        ("year_built", "number", "1800..2016", 2008, "Invalid values rejected; no median fallback."),
        ("floor_count", "number", "> 0", 4, "Invalid values rejected; no median fallback."),
        ("air_temperature", "number", "finite", 25.0, "Invalid values rejected."),
        ("cloud_coverage", "number", "finite", 6.0, "Invalid values rejected."),
        ("dew_temperature", "number", "finite", 20.0, "Invalid values rejected."),
        ("precip_depth_1_hr", "number", "finite", 0.0, "Negative sentinel values are accepted because training data contains them."),
        ("sea_level_pressure", "number", "finite", 1019.7, "Invalid values rejected."),
        ("wind_direction", "number", "0..360", 180.0, "Invalid values rejected."),
        ("wind_speed", "number", "finite", 3.1, "Invalid values rejected."),
    ]
    return {
        "schema_name": "energy-prediction-request", "schema_version": SCHEMA_VERSION,
        "additional_properties": False, "target_field_prohibited": "meter_reading",
        "building_id_required_despite_exclusion": True,
        "known_primary_use_values": known_uses,
        "fields": [{"name": n, "type": t, "required": True, "accepted_range": r,
                    "example": e, "validation_rule": r, "fallback_behaviour": "none",
                    "error_behaviour": b} for n,t,r,e,b in fields],
    }


def model_card(metadata: dict) -> str:
    v=metadata["validation_metrics"]; t=metadata["test_metrics"]
    return f"""# Energy Consumption Random Forest — {metadata['version']}

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

- Source: `data/processed/feature_dataset.parquet`, {metadata['dataset_rows']:,} observations
- Training: {metadata['split_rows']['train']:,} chronological rows through 2016-08-31
- Validation: {metadata['split_rows']['validation']:,} rows during September–October 2016
- Test: {metadata['split_rows']['test']:,} rows during November–December 2016
- Validation: RMSE {v['rmse']:.2f}, MAE {v['mae']:.2f}, R² {v['r2']:.4f}
- Test: RMSE {t['rmse']:.2f}, MAE {t['mae']:.2f}, R² {t['r2']:.4f}

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
"""


def read_ranges(parquet: pq.ParquetFile) -> dict:
    table = parquet.read(columns=["building_id", "site_id", "timestamp"])
    return {
        "building_id": {"min": int(pc.min(table["building_id"]).as_py()),
                        "max": int(pc.max(table["building_id"]).as_py())},
        "site_id": {"min": int(pc.min(table["site_id"]).as_py()),
                    "max": int(pc.max(table["site_id"]).as_py())},
        "timestamp": {"min": str(pc.min(table["timestamp"]).as_py()),
                      "max": str(pc.max(table["timestamp"]).as_py())},
    }


def main() -> None:
    a = args()
    for attr in ("source_model", "output_root", "metrics"):
        p=getattr(a,attr); setattr(a,attr,p if p.is_absolute() else (ROOT/p).resolve())
    a.manifest = (a.manifest if a.manifest else a.output_root/"current.json")
    if not a.manifest.is_absolute(): a.manifest=(ROOT/a.manifest).resolve()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"), logging.StreamHandler()])
    if not a.source_model.is_file(): raise FileNotFoundError(a.source_model)
    baseline=json.loads(a.metrics.read_text(encoding="utf-8"))
    advanced=json.loads(ADVANCED_METRICS.read_text(encoding="utf-8"))
    selected=baseline["models"]["random_forest"]
    if Path(selected["model_path"]).name != a.source_model.name:
        raise ValueError("Source model does not match baseline metrics.")
    if advanced["selection"]["recommended_candidate"] != "random_forest":
        raise ValueError("Advanced selection evidence does not recommend Random Forest.")
    pipeline=joblib.load(a.source_model)
    if list(pipeline.named_steps) != ["preprocessor","model"]:
        raise ValueError("Source artifact is not the expected fitted pipeline.")
    expected=baseline["predictors"]
    if list(pipeline.feature_names_in_) != expected:
        raise ValueError("Source feature order differs from baseline metrics.")
    categories=pipeline.named_steps["preprocessor"].named_transformers_[
        "categorical"].named_steps["onehot"].categories_
    uses=[str(x) for x in categories[0]]
    meters=[int(x) for x in categories[1]]
    if meters != [0,1,2,3]: raise ValueError("Unexpected fitted meter categories.")
    ranges=read_ranges(pq.ParquetFile(DATASET))
    source_fp=fingerprint(a.source_model)
    dataset_fp=fingerprint(DATASET)
    protected_before={
        str(p.relative_to(ROOT)).replace("\\","/"): fingerprint(p)
        for folder in (ROOT/"models/baseline",ROOT/"models/advanced")
        for p in folder.rglob("*") if p.is_file()}
    if a.dry_run:
        print(json.dumps({"status":"dry-run passed","source":source_fp,
                          "version_requested":a.version,"predictors":len(expected),
                          "transformed_features":len(pipeline.named_steps["preprocessor"].get_feature_names_out())},indent=2))
        return
    a.output_root.mkdir(parents=True,exist_ok=True)
    version=resolve_version(a.output_root,a.version,a.force_new_version)
    final=a.output_root/version
    temp=Path(tempfile.mkdtemp(prefix=f".{version}.build-",dir=a.output_root))
    created=datetime.now(timezone.utc).isoformat()
    try:
        shutil.copy2(a.source_model,temp/"model.joblib")
        schema=input_schema(uses)
        (temp/"feature_schema.json").write_text(json.dumps(schema,indent=2),encoding="utf-8")
        metadata={
            "model_name":"energy-consumption-random-forest","version":version,
            "created_at":created,"algorithm":"RandomForestRegressor",
            "estimator_parameters":pipeline.named_steps["model"].get_params(),
            "target":"meter_reading","target_strategy":"raw",
            "negative_prediction_rule":"clip raw predictions to zero and emit a warning",
            "training_date":baseline["generated_at_utc"],"source_dataset":dataset_fp["path"],
            "source_dataset_fingerprint":dataset_fp,"dataset_rows":baseline["dataset"]["rows"],
            "split_rows":{k:v["rows"] for k,v in baseline["splits"].items()},
            "split_boundaries":baseline["splits"],"training_data_coverage":"full",
            "predictor_count":len(expected),
            "transformed_feature_count":len(pipeline.named_steps["preprocessor"].get_feature_names_out()),
            "predictor_columns":expected,
            "transformed_feature_names":pipeline.named_steps["preprocessor"].get_feature_names_out().tolist(),
            "validation_metrics":selected["validation"],"test_metrics":selected["test"],
            "training_duration_seconds":selected["training_time_seconds"],
            "recorded_test_inference_seconds":selected["inference_time_seconds"]["test"],
            "source_artifact":source_fp,
            "packaged_artifact_size_bytes":(temp/"model.joblib").stat().st_size,
            "python_version":sys.version.split()[0],"scikit_learn_version":sklearn.__version__,
            "pandas_version":pd.__version__,"numpy_version":np.__version__,
            "joblib_version":joblib.__version__,"platform":platform.platform(),
            "feature_engineering_script_fingerprint":fingerprint(ROOT/"scripts/week2_feature_engineering.py"),
            "baseline_metrics_fingerprint":fingerprint(BASELINE_METRICS),
            "advanced_metrics_fingerprint":fingerprint(ADVANCED_METRICS),
            "input_schema_version":SCHEMA_VERSION,"feature_pipeline_version":FEATURE_PIPELINE_VERSION,
            "known_categories":{"primary_use":uses,"meter":meters},
            "training_identifier_ranges":{"building_id":ranges["building_id"],"site_id":ranges["site_id"]},
            "training_timestamp_range":ranges["timestamp"],
            "intended_use":"Non-critical energy meter-reading prediction and Week 3 API integration.",
            "prohibited_use":["billing","safety-critical control","guaranteed savings","unvalidated financial decisions"],
            "known_risks":["extreme-value sensitivity","late-period drift","low R-squared",
                           "meter-dependent units","unknown-category all-zero encoding"],
        }
        (temp/"model_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
        package_metrics={"selection_summary":{
            "best_advanced_validation_model":advanced["selection"]["best_advanced_candidate"],
            "best_advanced_test_model":advanced["selection"]["best_test_model"],
            "best_mae_model":"random_forest","recommended_production_model":"random_forest",
            "rationale":advanced["selection"]["rationale"]},
            "validation":selected["validation"],"test":selected["test"],
            "training_time_seconds":selected["training_time_seconds"],
            "recorded_inference_time_seconds":selected["inference_time_seconds"]}
        (temp/"metrics.json").write_text(json.dumps(package_metrics,indent=2),encoding="utf-8")
        requirements={"python":sys.version.split()[0],"packages":{
            "numpy":np.__version__,"pandas":pd.__version__,"scikit-learn":sklearn.__version__,
            "joblib":joblib.__version__},"install":"python -m pip install numpy pandas scikit-learn joblib",
            "compatibility_note":"Pin these versions for exact artifact compatibility."}
        (temp/"requirements.json").write_text(json.dumps(requirements,indent=2),encoding="utf-8")
        card=model_card(metadata)
        (temp/"model_card.md").write_text(card,encoding="utf-8")
        example={f["name"]:f["example"] for f in schema["fields"]}
        (temp/"example_request.json").write_text(json.dumps(example,indent=2),encoding="utf-8")
        # Generate the example from the actual copied pipeline and shared Task 2.3 formulas.
        from ml_service.inference import LoadedProductionModel, build_feature_frame
        loaded=LoadedProductionModel(joblib.load(temp/"model.joblib"),metadata,schema,temp,{})
        features,warnings=build_feature_frame([example],loaded)
        raw=float(loaded.pipeline.predict(features)[0]); prediction=max(0.0,raw)
        if raw<0: warnings[0].append("Negative model output was clipped to zero.")
        response={"predicted_meter_reading":prediction,"model_version":version,
            "prediction_timestamp":created,"input_timestamp":str(pd.Timestamp(example["timestamp"])),
            "warnings":warnings[0],
            "units":"Meter-dependent; meter codes may represent electricity, chilled water, steam, or hot water."}
        (temp/"example_response.json").write_text(json.dumps(response,indent=2),encoding="utf-8")
        readme=f"""# Production package {version}

Frozen Random Forest inference package. Load through `ml_service.inference`, not by reconstructing features.

```python
from ml_service.inference import predict_one
result = predict_one(request)
```

Reproduce with:

`python scripts/week2_package_production_model.py --version {version}`

Run validation with:

`python scripts/test_production_inference.py`

The package does not load training data, retrain, expose an API endpoint, or deploy anything.
"""
        (temp/"README.md").write_text(readme,encoding="utf-8")
        package_names=["model.joblib","feature_schema.json","model_metadata.json","metrics.json",
                       "requirements.json","model_card.md","example_request.json","example_response.json","README.md"]
        source_names=["scripts/week2_feature_engineering.py","ml_service/inference.py",
                      "scripts/week2_package_production_model.py",
                      "reports/week2_baseline_metrics.json","reports/week2_advanced_metrics.json"]
        checksums={"algorithm":"SHA-256",
            "package_files":{n:sha256(temp/n) for n in package_names},
            "source_files":{n:sha256(ROOT/n) for n in source_names}}
        (temp/"checksums.json").write_text(json.dumps(checksums,indent=2),encoding="utf-8")
        # Candidate manifest enables a full checksum/load/predict test before activation.
        candidate=a.output_root/"candidate_manifest.tmp.json"
        candidate_data={"active_version":version,"version_directory":temp.name,
            "model_path":"model.joblib","created_at":created,"algorithm":"RandomForestRegressor",
            "input_schema_version":SCHEMA_VERSION,"feature_pipeline_version":FEATURE_PIPELINE_VERSION}
        atomic_json(candidate,candidate_data)
        from ml_service.inference import load_production_model, predict_one, verify_package_checksums
        verify_package_checksums(temp)
        tested=load_production_model(candidate)
        result=predict_one(example,candidate)
        if tested.metadata["version"]!=version or not np.isfinite(result["predicted_meter_reading"]) or result["predicted_meter_reading"]<0:
            raise RuntimeError("Candidate package inference validation failed.")
        candidate.unlink()
        os.replace(temp,final)
        manifest={"active_version":version,"version_directory":version,"model_path":"model.joblib",
            "created_at":created,"algorithm":"RandomForestRegressor",
            "input_schema_version":SCHEMA_VERSION,"feature_pipeline_version":FEATURE_PIPELINE_VERSION}
        atomic_json(a.manifest,manifest)
        protected_after={k:fingerprint(ROOT/k) for k in protected_before}
        if protected_before!=protected_after:
            raise RuntimeError("Protected baseline or advanced artifacts changed.")
        logging.info("Activated validated production package %s",version)
        print(json.dumps({"status":"packaged","version":version,
            "source_sha256":source_fp["sha256"],"production_sha256":sha256(final/"model.joblib"),
            "example_prediction":result["predicted_meter_reading"]},indent=2))
    except Exception:
        if temp.exists(): shutil.rmtree(temp,ignore_errors=True)
        candidate=a.output_root/"candidate_manifest.tmp.json"
        if candidate.exists(): candidate.unlink()
        raise


if __name__=="__main__":
    main()
