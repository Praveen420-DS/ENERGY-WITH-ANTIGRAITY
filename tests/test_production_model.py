import json
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np

from ml_service.inference import (build_feature_frame, load_production_model,
                                  predict_batch, verify_package_checksums)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "models/production/current.json"


def test_package_manifest_and_checksums():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["active_version"] == "v1.0.0"
    package = MANIFEST.parent / manifest["version_directory"]
    required = {"model.joblib", "feature_schema.json", "model_metadata.json",
                "metrics.json", "requirements.json", "model_card.md",
                "example_request.json", "example_response.json",
                "checksums.json", "README.md"}
    assert required <= {p.name for p in package.iterdir()}
    assert verify_package_checksums(package)["algorithm"] == "SHA-256"


def test_loadability_determinism_and_output_contract():
    loaded = load_production_model(MANIFEST)
    request = json.loads((loaded.package_dir/"example_request.json").read_text())
    first = predict_batch([request, request], MANIFEST)
    second = predict_batch([request, request], MANIFEST)
    assert len(first) == 2
    assert [x["predicted_meter_reading"] for x in first] == [
        x["predicted_meter_reading"] for x in second]
    assert all(isinstance(x["predicted_meter_reading"], float) for x in first)
    assert all(np.isfinite(x["predicted_meter_reading"]) and
               x["predicted_meter_reading"] >= 0 for x in first)


def test_packaged_model_matches_original_on_deterministic_sample():
    loaded = load_production_model(MANIFEST)
    example = json.loads((loaded.package_dir/"example_request.json").read_text())
    start = datetime.fromisoformat(example["timestamp"].replace("Z", "+00:00"))
    records = []
    for index in range(25):
        record = dict(example)
        record["timestamp"] = (start + timedelta(hours=index)).isoformat()
        for field, scale in (("air_temperature", 0.25), ("dew_temperature", 0.15),
                             ("wind_speed", 0.1)):
            if field in record and record[field] is not None:
                record[field] = float(record[field]) + (index % 7) * scale
        if "cloud_coverage" in record and record["cloud_coverage"] is not None:
            record["cloud_coverage"] = (int(record["cloud_coverage"]) + index) % 10
        records.append(record)
    features, _ = build_feature_frame(records, loaded)
    source = joblib.load(ROOT/"models/baseline/random_forest.joblib")
    source_predictions = np.maximum(source.predict(features), 0)
    packaged_predictions = np.array([
        x["predicted_meter_reading"] for x in predict_batch(records, MANIFEST)])
    np.testing.assert_allclose(packaged_predictions, source_predictions, rtol=0, atol=1e-10)
