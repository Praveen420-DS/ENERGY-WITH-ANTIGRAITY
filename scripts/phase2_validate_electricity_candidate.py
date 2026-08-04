"""Checksum-first, production-isolated validator for the electricity candidate."""
from __future__ import annotations
import hashlib, importlib.metadata, json, math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

REQUIRED = {"model.joblib","model_metadata.json","metrics.json","feature_schema.json","requirements.json","checksums.json","model_card.md","README.md","example_request.json","example_response.json","validation_report.json","validation_report.md"}

class CandidateValidationError(ValueError): pass

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(8*1024*1024),b""): h.update(b)
    return h.hexdigest()

def validate_checksums(package: Path) -> dict:
    package=Path(package); missing=sorted(REQUIRED-{p.name for p in package.iterdir() if p.is_file()})
    if missing: raise CandidateValidationError(f"Required package files missing: {missing}")
    manifest=json.loads((package/"checksums.json").read_text(encoding="utf-8"))
    for name, expected in manifest["package_files"].items():
        path=package/name
        if not path.is_file() or digest(path)!=expected: raise CandidateValidationError(f"Checksum validation failed: {name}")
    return manifest

def validate_dependencies(package: Path) -> dict:
    req=json.loads((Path(package)/"requirements.json").read_text(encoding="utf-8")); actual={}
    for name, expected in req["python_packages"].items():
        value=importlib.metadata.version(name); actual[name]=value
        if value!=expected: raise CandidateValidationError(f"Dependency mismatch for {name}: expected {expected}, found {value}")
    return actual

def load_candidate(package: Path):
    validate_checksums(package); validate_dependencies(package)
    import joblib
    artifact=joblib.load(Path(package)/"model.joblib")
    if type(artifact.get("model")).__name__!="RandomForestRegressor" or "preprocessor" not in artifact: raise CandidateValidationError("Artifact structure or estimator type is invalid.")
    return artifact

def validate_request(payload: dict, schema: dict) -> pd.DataFrame:
    if "meter" in payload and payload["meter"] != 0: raise CandidateValidationError("Only electricity meter code 0 is accepted.")
    if "features" not in payload or "input_timestamp" not in payload: raise CandidateValidationError("Request requires input_timestamp and features.")
    try: pd.Timestamp(payload["input_timestamp"])
    except Exception as exc: raise CandidateValidationError("Invalid input_timestamp.") from exc
    features=payload["features"]; ordered=schema["ordered_input_columns"]
    missing=[c for c in ordered if c not in features]; extra=[c for c in features if c not in ordered]
    if missing or extra: raise CandidateValidationError(f"Feature schema mismatch; missing={missing}, extra={extra}")
    if list(features)!=ordered: raise CandidateValidationError("Feature order does not match packaged schema.")
    for name in schema["numeric_columns"]:
        value=features[name]
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value))): raise CandidateValidationError(f"Invalid numeric feature: {name}")
    for name in schema["categorical_columns"]:
        if not isinstance(features[name],str) or not features[name].strip(): raise CandidateValidationError(f"Invalid categorical feature: {name}")
    return pd.DataFrame([{c:features[c] for c in ordered}],columns=ordered)

def predict(package: Path, payload: dict) -> dict:
    package=Path(package); artifact=load_candidate(package)
    schema=json.loads((package/"feature_schema.json").read_text(encoding="utf-8")); frame=validate_request(payload,schema)
    transformed=artifact["preprocessor"].transform(frame); raw=float(artifact["model"].predict(transformed)[0])
    if not math.isfinite(raw): raise CandidateValidationError("Prediction is not finite.")
    warnings=[]
    known=schema.get("known_categories",{})
    for name in schema["categorical_columns"]:
        if known.get(name) and payload["features"][name] not in known[name]: warnings.append(f"Unknown category for {name}; fitted encoder ignored it safely.")
    value=max(0.0,raw)
    if raw<0: warnings.append("Raw negative prediction clipped to zero as documented.")
    meta=json.loads((package/"model_metadata.json").read_text(encoding="utf-8"))
    return {"predicted_electricity_consumption_value":value,"model_version":meta["model_version"],"dataset_scope":"electricity_only","prediction_timestamp":datetime.now(timezone.utc).isoformat(),"input_timestamp":payload["input_timestamp"],"output_unit":"unverified","warnings":warnings}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("package",type=Path); p.add_argument("--request",type=Path); a=p.parse_args()
    request=a.request or a.package/"example_request.json"; print(json.dumps(predict(a.package,json.loads(request.read_text(encoding="utf-8"))),indent=2))
