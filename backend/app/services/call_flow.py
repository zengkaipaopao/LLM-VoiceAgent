from datetime import datetime

from app.repositories.calls import call_repository
from app.schemas.calls import CallCreate, CallLog


class CallFlowService:
    def list_calls(self) -> list[CallLog]:
        return list(call_repository.list())

    def create_outbound_call(self, payload: CallCreate) -> CallLog:
        call = CallLog(
            id=f"call_{len(call_repository.list()) + 1}",
            direction="outbound",
            counterpart=payload.counterpart,
            started_at=datetime.now(),
            duration_seconds=0,
            status="ongoing",
            summary=None,
        )
        return call_repository.create(call)


call_flow_service = CallFlowService()
