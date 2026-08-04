import hashlib,json,math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.dependencies import get_current_user
from app.ml.electricity_candidate_manager import ElectricityCandidateManager,get_electricity_candidate_manager
from app.middleware.electricity_candidate_rate_limiter import ElectricityCandidateRateLimiter

ROOT=Path(__file__).resolve().parents[2]; PACKAGE=ROOT/"models/candidates/v2.0.0-electricity"
def request():
    value=json.loads((PACKAGE/"example_request.json").read_text()); value["meter"]=0; return value
def hash_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def test_candidate_disabled_by_default_and_settings_path_safety():
    assert Settings().electricity_candidate_enabled is False
    with pytest.raises(ValueError): Settings(ELECTRICITY_CANDIDATE_PACKAGE="../unsafe")

def test_candidate_rate_limit_matches_prediction_policy():
    limiter=ElectricityCandidateRateLimiter(rate=10,capacity=20)
    assert all(limiter.allow("client",now=0) for _ in range(20)); assert limiter.allow("client",now=0) is False; assert limiter.allow("client",now=.1) is True

def test_manager_enabled_health_prediction_determinism_and_parity():
    manager=ElectricityCandidateManager(); manager.load("models/candidates/v2.0.0-electricity")
    assert manager.readiness(True).status=="ready"
    first=manager.predict(request()); second=manager.predict(request())
    expected=json.loads((PACKAGE/"example_response.json").read_text())["predicted_electricity_consumption_value"]
    assert first[0]==pytest.approx(second[0],abs=1e-10)==pytest.approx(expected,abs=1e-10); assert math.isfinite(first[0])

@pytest.mark.parametrize("meter",[1,2,3])
def test_non_electricity_rejected(meter):
    manager=ElectricityCandidateManager(); manager.load("models/candidates/v2.0.0-electricity"); payload=request(); payload["meter"]=meter
    with pytest.raises(ValueError): manager.predict(payload)

def test_missing_invalid_unknown_and_no_persistence_contract():
    manager=ElectricityCandidateManager(); manager.load("models/candidates/v2.0.0-electricity")
    payload=request(); payload["features"].pop(next(iter(payload["features"])))
    with pytest.raises(ValueError): manager.predict(payload)
    payload=request(); payload["features"]["square_feet"]=float("inf")
    with pytest.raises(ValueError): manager.predict(payload)
    payload=request(); payload["features"]["primary_use"]="Unknown Safe Use"; value,warnings,_=manager.predict(payload)
    assert math.isfinite(value) and warnings

def test_corruption_failure_isolated_from_production(tmp_path):
    import shutil
    trusted=tmp_path/"candidates"; copy=trusted/"v2.0.0-electricity"; shutil.copytree(PACKAGE,copy)
    with (copy/"model.joblib").open("ab") as stream: stream.write(b"bad")
    manager=ElectricityCandidateManager(trusted)
    with pytest.raises(Exception): manager.load(str(copy.relative_to(Path.cwd())) if copy.is_relative_to(Path.cwd()) else str(copy))
    assert get_electricity_candidate_manager() is not manager

def test_production_files_unchanged_and_response_contract():
    assert hash_file(ROOT/"models/production/current.json")==hash_file(ROOT/"models/production/current.json")
    response=json.loads((PACKAGE/"example_response.json").read_text()); assert "confidence" not in response and response["output_unit"]=="unverified"

def test_http_disabled_health_and_authentication_required():
    app=create_app(Settings(ELECTRICITY_CANDIDATE_ENABLED=False)); client=TestClient(app)
    health=client.get("/api/electricity-candidate/health"); assert health.status_code==503 and health.json()["status"]=="disabled"
    assert client.post("/api/electricity-candidate/predict",json=request()).status_code==401

def test_http_enabled_prediction_contract():
    manager=get_electricity_candidate_manager(); manager.load("models/candidates/v2.0.0-electricity")
    app=create_app(Settings(ELECTRICITY_CANDIDATE_ENABLED=True)); app.dependency_overrides[get_current_user]=lambda: object(); client=TestClient(app)
    response=client.post("/api/electricity-candidate/predict",json=request()); assert response.status_code==200
    body=response.json(); expected=json.loads((PACKAGE/"example_response.json").read_text())["predicted_electricity_consumption_value"]
    assert body["predicted_electricity_consumption_value"]==pytest.approx(expected,abs=1e-10)
    assert body["model_status"]=="candidate" and body["output_unit"]=="unverified" and "confidence" not in body
    assert client.get("/api/electricity-candidate/health").json()["status"]=="ready"; manager.clear()

def test_http_structured_validation_and_unsupported_meter_errors():
    manager=get_electricity_candidate_manager(); manager.load("models/candidates/v2.0.0-electricity")
    app=create_app(Settings(ELECTRICITY_CANDIDATE_ENABLED=True)); app.dependency_overrides[get_current_user]=lambda: object(); client=TestClient(app)
    payload=request(); payload["input_timestamp"]="not-a-time"; response=client.post("/api/electricity-candidate/predict",json=payload)
    assert response.status_code==422 and response.json()["error"]["code"]=="INVALID_CANDIDATE_INPUT" and response.json()["error"]["request_id"]
    payload=request(); payload["meter"]=1; response=client.post("/api/electricity-candidate/predict",json=payload)
    assert response.status_code==400 and response.json()["error"]["code"]=="UNSUPPORTED_METER"; manager.clear()
