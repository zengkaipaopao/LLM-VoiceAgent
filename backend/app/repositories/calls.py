from __future__ import annotations

from datetime import datetime
from typing import Iterable

from app.schemas.calls import CallLog


class CallRepository:
    """In-memory repository placeholder. Replace with DB/ORM implementation."""

    def __init__(self) -> None:
        self._items: list[CallLog] = [
            CallLog(
                id="call_1",
                direction="outbound",
                counterpart="+1 415 555 0101",
                started_at=datetime.now(),
                duration_seconds=420,
                status="completed",
                summary="首次接触完成。",
            )
        ]

    def list(self) -> Iterable[CallLog]:
        return self._items

    def create(self, call: CallLog) -> CallLog:
        self._items.append(call)
        return call


call_repository = CallRepository()
