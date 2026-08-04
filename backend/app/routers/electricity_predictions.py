from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Response,status
from fastapi.concurrency import run_in_threadpool
from app.dependencies import get_current_user
from app.ml.electricity_candidate_manager import get_electricity_candidate_manager
from app.schemas.electricity_prediction import ElectricityCandidateHealth,ElectricityCandidateRequest,ElectricityCandidateResponse
from app.services.electricity_prediction_service import ElectricityPredictionService,ElectricityPredictionServiceError
from app.middleware.electricity_candidate_rate_limiter import candidate_rate_limiter

router=APIRouter()
def error(code,message,request_id,status_code):
    return HTTPException(status_code=status_code,detail={"error":{"code":code,"message":message,"request_id":request_id,"timestamp":datetime.now(timezone.utc).isoformat()}})

@router.get("/health",response_model=ElectricityCandidateHealth)
async def health(request:Request,response:Response):
    enabled=request.app.state.settings.electricity_candidate_enabled; ready=get_electricity_candidate_manager().readiness(enabled)
    if ready.status!="ready": response.status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    return ElectricityCandidateHealth(**ready.__dict__)

@router.post("/predict",response_model=ElectricityCandidateResponse,summary="Experimental electricity candidate prediction")
async def predict(body:ElectricityCandidateRequest,request:Request,current_user=Depends(get_current_user)):
    del current_user
    client_key=request.client.host if request.client else "unknown"
    if not candidate_rate_limiter.allow(client_key): raise error("RATE_LIMIT_EXCEEDED","The candidate prediction rate limit was exceeded.",request.state.request_id,429)
    if not request.app.state.settings.electricity_candidate_enabled: raise error("CANDIDATE_DISABLED","The experimental electricity candidate is disabled.",request.state.request_id,503)
    if not get_electricity_candidate_manager().readiness(True).model_loaded: raise error("CANDIDATE_UNAVAILABLE","The experimental electricity candidate is unavailable.",request.state.request_id,503)
    try: return await run_in_threadpool(ElectricityPredictionService.predict,body,get_electricity_candidate_manager())
    except ElectricityPredictionServiceError as exc:
        message=str(exc); code="UNSUPPORTED_METER" if "meter code 0" in message else "INVALID_CANDIDATE_INPUT"
        raise error(code,"The candidate request is invalid.",request.state.request_id,400) from exc
