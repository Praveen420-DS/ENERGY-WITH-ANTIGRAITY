"""Independent lifecycle for the inactive electricity candidate."""
from __future__ import annotations
import json, logging, math, threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from scripts.phase2_validate_electricity_candidate import CandidateValidationError, validate_checksums, validate_dependencies, validate_request

LOGGER=logging.getLogger(__name__)
class ElectricityCandidateError(RuntimeError): pass

@dataclass(frozen=True)
class CandidateReadiness:
    status:str; enabled:bool; model_loaded:bool; model_version:str|None; checksum_status:str

class ElectricityCandidateManager:
    def __init__(self, trusted_root: Path|None=None):
        self.trusted_root=(trusted_root or Path.cwd()/"models/candidates").resolve(); self._artifact=None; self._metadata=None; self._schema=None; self._lock=threading.RLock(); self._error=False
    def load(self, package_value: str):
        package=(Path.cwd()/package_value).resolve()
        if package.parent != self.trusted_root: raise ElectricityCandidateError("Candidate package configuration is not trusted.")
        try:
            validate_checksums(package); validate_dependencies(package)
            import joblib
            artifact=joblib.load(package/"model.joblib"); metadata=json.loads((package/"model_metadata.json").read_text()); schema=json.loads((package/"feature_schema.json").read_text())
            if type(artifact.get("model")).__name__!="RandomForestRegressor" or "preprocessor" not in artifact: raise CandidateValidationError("Invalid candidate artifact.")
            self._artifact,self._metadata,self._schema=artifact,metadata,schema; self._error=False
            LOGGER.info("Electricity candidate loaded version=%s status=candidate checksum=verified",metadata["model_version"])
        except Exception as exc:
            self.clear(); self._error=True; LOGGER.error("Electricity candidate unavailable category=validation"); raise ElectricityCandidateError("Candidate validation failed.") from exc
    def clear(self): self._artifact=self._metadata=self._schema=None
    def readiness(self, enabled: bool):
        if not enabled: return CandidateReadiness("disabled",False,False,None,"not_verified")
        if self._artifact is None: return CandidateReadiness("unavailable",True,False,None,"not_verified")
        return CandidateReadiness("ready",True,True,self._metadata["model_version"],"verified")
    def predict(self, payload: dict):
        if self._artifact is None: raise ElectricityCandidateError("Candidate is unavailable.")
        frame=validate_request(payload,self._schema)
        with self._lock: raw=float(self._artifact["model"].predict(self._artifact["preprocessor"].transform(frame))[0])
        if not math.isfinite(raw): raise ElectricityCandidateError("Candidate returned an invalid result.")
        warnings=[]
        for name in self._schema["categorical_columns"]:
            if payload["features"][name] not in self._schema["known_categories"].get(name,[]): warnings.append(f"Unknown category for {name}; fitted encoder ignored it safely.")
        value=max(0.0,raw)
        if raw<0: warnings.append("Raw negative prediction clipped to zero as documented.")
        return value,warnings,self._metadata["model_version"]

_manager=ElectricityCandidateManager()
def get_electricity_candidate_manager(): return _manager
