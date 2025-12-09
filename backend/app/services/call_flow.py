from datetime import datetime

from app.repositories.calls import CallRepository, call_repository
from app.schemas.calls import CallCreate, CallLog


class CallFlowService:
    def __init__(self, repository: CallRepository | None = None) -> None:
        self._repository = repository or call_repository

    def list_calls(self) -> list[CallLog]:
        return list(self._repository.list())

    def create_outbound_call(self, payload: CallCreate) -> CallLog:
        call = CallLog(
            id=f"call_{len(self._repository.list()) + 1}",
            direction="outbound",
            counterpart=payload.counterpart,
            started_at=datetime.now(),
            duration_seconds=0,
            status="ongoing",
            summary=None,
        )
        return self._repository.create(call)


call_flow_service = CallFlowService()
