from __future__ import annotations
import hashlib, json, math, shutil
from pathlib import Path
import pytest

from scripts.phase2_validate_electricity_candidate import CandidateValidationError, REQUIRED, load_candidate, predict, validate_checksums

ROOT=Path(__file__).resolve().parents[1]; PACKAGE=ROOT/"models/candidates/v2.0.0-electricity"

def tree_hash(path: Path) -> str:
    digest=hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()): digest.update(str(item.relative_to(path)).encode()); digest.update(item.read_bytes())
    return digest.hexdigest()

PRODUCTION_CURRENT=(ROOT/"models/production/current.json").read_bytes()
PRODUCTION_V1_HASH=tree_hash(ROOT/"models/production/v1.0.0")

def request(): return json.loads((PACKAGE/"example_request.json").read_text())

def test_required_package_files_and_checksums():
    assert REQUIRED <= {p.name for p in PACKAGE.iterdir()}; assert validate_checksums(PACKAGE)["algorithm"]=="SHA-256"

def test_corrupted_artifact_rejected(tmp_path):
    copy=tmp_path/"package"; shutil.copytree(PACKAGE,copy)
    with (copy/"model.joblib").open("ab") as stream: stream.write(b"corruption")
    with pytest.raises(CandidateValidationError,match="Checksum"): load_candidate(copy)

def test_model_and_metadata_load():
    artifact=load_candidate(PACKAGE); metadata=json.loads((PACKAGE/"model_metadata.json").read_text())
    assert type(artifact["model"]).__name__=="RandomForestRegressor"; assert metadata["release_status"]=="candidate"

def test_valid_deterministic_finite_prediction_and_example_parity():
    first=predict(PACKAGE,request()); second=predict(PACKAGE,request()); example=json.loads((PACKAGE/"example_response.json").read_text())
    assert first["predicted_electricity_consumption_value"]==pytest.approx(second["predicted_electricity_consumption_value"],abs=1e-10)
    assert first["predicted_electricity_consumption_value"]==pytest.approx(example["predicted_electricity_consumption_value"],abs=1e-10)
    assert math.isfinite(first["predicted_electricity_consumption_value"]); assert "confidence" not in first

def test_feature_order_missing_and_invalid_numeric_rejected():
    payload=request(); payload["features"]={k:payload["features"][k] for k in reversed(payload["features"])}
    with pytest.raises(CandidateValidationError,match="order"): predict(PACKAGE,payload)
    payload=request(); payload["features"].pop(next(iter(payload["features"])))
    with pytest.raises(CandidateValidationError,match="missing"): predict(PACKAGE,payload)
    payload=request(); payload["features"]["square_feet"]=float("inf")
    with pytest.raises(CandidateValidationError,match="numeric"): predict(PACKAGE,payload)

def test_non_electricity_rejected_and_unknown_category_safe():
    payload=request(); payload["meter"]=1
    with pytest.raises(CandidateValidationError,match="meter code 0"): predict(PACKAGE,payload)
    payload=request(); payload["features"]["primary_use"]="Never-seen safe category"
    result=predict(PACKAGE,payload); assert result["warnings"] and math.isfinite(result["predicted_electricity_consumption_value"])

def test_negative_output_policy_documented():
    readme=(PACKAGE/"model_card.md").read_text().lower(); source=(ROOT/"scripts/phase2_validate_electricity_candidate.py").read_text().lower()
    assert "negative" in source and "clip" in source; assert "production" in readme

def test_schema_excludes_meter_timestamp_target_and_target_derivations():
    schema=json.loads((PACKAGE/"feature_schema.json").read_text()); columns=schema["ordered_input_columns"]
    assert not {"meter","timestamp","meter_reading"}&set(columns); assert schema["meter_removed_from_predictors"] is True; assert schema["target_derived_features"] is False

def test_production_isolation_unchanged():
    assert (ROOT/"models/production/current.json").read_bytes()==PRODUCTION_CURRENT
    assert tree_hash(ROOT/"models/production/v1.0.0")==PRODUCTION_V1_HASH
