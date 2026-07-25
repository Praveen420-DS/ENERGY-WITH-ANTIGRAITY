"""Executable smoke, parity, contract, checksum, and latency validation."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_service import inference
from ml_service.inference import (InputValidationError, LoadedProductionModel,
    build_feature_frame, get_model_metadata, load_production_model,
    predict_batch, predict_one, validate_prediction_input,
    verify_package_checksums)

RESULT_PATH = ROOT / "reports/week2_production_smoke_results.json"


def expect_validation_error(record: dict) -> bool:
    try:
        validate_prediction_input(record)
    except InputValidationError:
        return True
    return False


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values), p))


def main() -> None:
    manifest = ROOT / "models/production/current.json"
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    package = manifest.parent / manifest_data["version_directory"]
    example = json.loads((package/"example_request.json").read_text(encoding="utf-8"))
    expected_response = json.loads((package/"example_response.json").read_text(encoding="utf-8"))
    checks = {}

    start=time.perf_counter(); loaded=load_production_model(manifest); cold=time.perf_counter()-start
    checks["model_loading"] = loaded.metadata["version"] == manifest_data["active_version"]
    checks["checksum_validation"] = bool(verify_package_checksums(package))
    single=predict_one(example,manifest)
    checks["single_prediction"] = np.isfinite(single["predicted_meter_reading"]) and single["predicted_meter_reading"] >= 0
    batch=predict_batch([example]*10,manifest)
    checks["batch_prediction"] = len(batch)==10 and all(np.isfinite(x["predicted_meter_reading"]) for x in batch)
    checks["deterministic_prediction"] = predict_one(example,manifest)["predicted_meter_reading"] == predict_one(example,manifest)["predicted_meter_reading"]
    checks["known_category"] = len(single["warnings"]) == 0
    unknown=dict(example,primary_use="Unseen experimental facility",building_id=999999,site_id=999999)
    normalized,warnings=validate_prediction_input(unknown,loaded)
    unknown_response=predict_one(unknown,manifest)
    checks["unsupported_category"] = len(warnings)>=3 and len(unknown_response["warnings"])>=3
    missing=dict(example); missing.pop("square_feet")
    checks["missing_required_field"] = expect_validation_error(missing)
    invalid=dict(example,square_feet=float("nan"))
    checks["invalid_numeric"] = expect_validation_error(invalid)
    checks["invalid_timestamp"] = expect_validation_error(dict(example,timestamp="not-a-date"))
    for meter in range(4):
        assert predict_one(dict(example,meter=meter),manifest)["predicted_meter_reading"] >= 0
    checks["every_meter_code"] = True

    class NegativePipeline:
        feature_names_in_ = np.asarray(loaded.metadata["predictor_columns"], dtype=object)
        def predict(self, frame): return np.full(len(frame), -5.0)
    negative_loaded=LoadedProductionModel(NegativePipeline(),loaded.metadata,loaded.schema,loaded.package_dir,loaded.manifest)
    with patch("ml_service.inference.load_production_model",return_value=negative_loaded):
        negative=predict_one(example,manifest)
    checks["negative_prediction_handling"] = negative["predicted_meter_reading"]==0 and any("clipped" in x for x in negative["warnings"])
    reordered={k:example[k] for k in reversed(list(example))}
    checks["feature_order_consistency"] = predict_one(reordered,manifest)["predicted_meter_reading"] == single["predicted_meter_reading"]
    checks["metadata_retrieval"] = get_model_metadata(manifest)["version"] == manifest_data["active_version"]
    checks["response_contract"] = set(single)==set(expected_response)

    features,_=build_feature_frame([example],loaded)
    original=joblib.load(ROOT/"models/baseline/random_forest.joblib")
    original_value=max(0.0,float(original.predict(features)[0]))
    checks["source_package_prediction_parity"] = bool(np.isclose(original_value,single["predicted_meter_reading"],rtol=0,atol=1e-10))

    timings={}
    for size in (1,10,100,1000):
        records=[example]*size
        samples=[]
        for _ in range(5):
            start=time.perf_counter(); predict_batch(records,manifest); samples.append(time.perf_counter()-start)
        median=percentile(samples,50)
        timings[str(size)]={"median_seconds":median,"p95_seconds":percentile(samples,95),
            "throughput_records_per_second":size/median}
    process=psutil.Process(os.getpid())
    result={"status":"passed" if all(checks.values()) else "failed","checks":checks,
        "cold_load_seconds":cold,"warm_latency":timings,
        "process_rss_mb":process.memory_info().rss/2**20,
        "example_prediction":single,"unknown_category_prediction":unknown_response}
    RESULT_PATH.write_text(json.dumps(result,indent=2),encoding="utf-8")
    if not all(checks.values()):
        failed=[k for k,v in checks.items() if not v]
        raise AssertionError(f"Smoke checks failed: {failed}")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
