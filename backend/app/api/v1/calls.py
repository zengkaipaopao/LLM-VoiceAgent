from fastapi import APIRouter

from app.schemas.calls import CallCreate, PaginatedCallResponse
from app.services.call_flow import call_flow_service

router = APIRouter()


@router.get("", response_model=PaginatedCallResponse)
async def list_calls() -> PaginatedCallResponse:
    calls = call_flow_service.list_calls()
    return PaginatedCallResponse(data=calls, total=len(calls))


@router.post("/outbound")
async def create_outbound_call(payload: CallCreate):
    call = call_flow_service.create_outbound_call(payload)
    return {"call": call}
