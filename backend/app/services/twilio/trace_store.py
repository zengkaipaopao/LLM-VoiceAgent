from app.services.twilio.runtime_backends import get_twilio_trace_store


async def _append_call_trace(
    call_sid: str | None,
    *,
    event_type: str,
    text: str | None = None,
    final: bool | None = None,
    level: str = "info",
) -> None:
    await get_twilio_trace_store().append_event(
        call_sid,
        event_type=event_type,
        text=text,
        final=final,
        level=level,
    )


async def _read_call_trace(call_sid: str, since: int) -> tuple[list[dict[str, object]], int]:
    return await get_twilio_trace_store().read_events(call_sid, since)


async def _read_latest_trace_call_sid() -> str | None:
    return await get_twilio_trace_store().read_latest_call_sid()
