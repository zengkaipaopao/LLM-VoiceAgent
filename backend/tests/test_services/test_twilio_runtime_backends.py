import pytest

from app.services.twilio.runtime_backends import (
    InMemoryTwilioStreamRuntimeStore,
    InMemoryTwilioTraceStore,
)


@pytest.mark.asyncio
async def test_in_memory_twilio_trace_store_filters_by_sequence_and_tracks_latest_call():
    store = InMemoryTwilioTraceStore()

    await store.append_event("CA001", event_type="stream_start", text="ready", level="success")
    await store.append_event("CA001", event_type="input_transcript", text="hello")
    await store.append_event("CA002", event_type="stream_start", text="next")

    events, last_seq = await store.read_events("CA001", since=0)

    assert last_seq == 2
    assert [item["type"] for item in events] == ["stream_start", "input_transcript"]
    assert await store.read_latest_call_sid() == "CA002"

    filtered, filtered_last_seq = await store.read_events("CA001", since=1)
    assert filtered_last_seq == 2
    assert len(filtered) == 1
    assert filtered[0]["type"] == "input_transcript"


@pytest.mark.asyncio
async def test_in_memory_twilio_trace_store_evicts_stale_calls_when_capacity_is_exceeded():
    store = InMemoryTwilioTraceStore(max_calls=2, max_events_per_call=4)

    await store.append_event("CA001", event_type="a")
    await store.append_event("CA002", event_type="b")
    await store.append_event("CA003", event_type="c")

    events_1, last_seq_1 = await store.read_events("CA001", since=0)
    events_3, last_seq_3 = await store.read_events("CA003", since=0)

    assert events_1 == []
    assert last_seq_1 == 0
    assert len(events_3) == 1
    assert last_seq_3 == 1


@pytest.mark.asyncio
async def test_in_memory_twilio_stream_runtime_store_tracks_active_calls_and_drains_manual_audio():
    store = InMemoryTwilioStreamRuntimeStore()

    assert await store.is_active("CA001") is False
    assert await store.drain_manual_audio("CA001") == []

    await store.mark_active("CA001")
    await store.mark_active("CA002")
    assert await store.is_active("CA001") is True
    assert await store.list_active_calls() == ["CA001", "CA002"]

    size_after_first = await store.enqueue_manual_audio("CA001", b"abc")
    size_after_second = await store.enqueue_manual_audio("CA001", b"def")
    drained = await store.drain_manual_audio("CA001")

    assert size_after_first == 1
    assert size_after_second == 2
    assert drained == [b"abc", b"def"]
    assert await store.drain_manual_audio("CA001") == []

    await store.mark_inactive("CA001")
    assert await store.is_active("CA001") is False
    assert await store.list_active_calls() == ["CA002"]
