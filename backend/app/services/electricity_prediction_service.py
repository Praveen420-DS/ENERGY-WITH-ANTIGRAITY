from datetime import datetime, timezone
from app.ml.electricity_candidate_manager import ElectricityCandidateError, ElectricityCandidateManager
from app.schemas.electricity_prediction import ElectricityCandidateRequest, ElectricityCandidateResponse

class ElectricityPredictionServiceError(RuntimeError): pass
class ElectricityPredictionService:
    @staticmethod
    def predict(request:ElectricityCandidateRequest,manager:ElectricityCandidateManager):
        payload={"input_timestamp":request.input_timestamp.isoformat(),"features":request.features}
        if request.meter is not None: payload["meter"]=request.meter
        try: value,warnings,version=manager.predict(payload)
        except (ElectricityCandidateError,ValueError) as exc: raise ElectricityPredictionServiceError(str(exc)) from exc
        return ElectricityCandidateResponse(predicted_electricity_consumption_value=value,model_version=version,prediction_timestamp=datetime.now(timezone.utc),input_timestamp=request.input_timestamp,warnings=warnings)
