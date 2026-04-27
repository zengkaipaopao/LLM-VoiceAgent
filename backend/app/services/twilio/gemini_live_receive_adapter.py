from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import AsyncIterator, Protocol


class GeminiReceiveSession(Protocol):
    def receive(self) -> AsyncIterator[object]: ...


@dataclass(slots=True)
class GeminiLiveSetupCompleteEvent:
    session_id: str | None


@dataclass(slots=True)
class GeminiInputTranscriptEvent:
    text: str
    final: bool


@dataclass(slots=True)
class GeminiOutputTranscriptEvent:
    text: str
    final: bool


@dataclass(slots=True)
class GeminiInterruptedEvent:
    pass


@dataclass(slots=True)
class GeminiAssistantMetaTextEvent:
    text: str


@dataclass(slots=True)
class GeminiAssistantAudioEvent:
    pcm_bytes: bytes
    mime_type: str | None


@dataclass(slots=True)
class GeminiTurnCompleteEvent:
    reason: str


GeminiLiveReceiveEvent = (
    GeminiLiveSetupCompleteEvent
    | GeminiInputTranscriptEvent
    | GeminiOutputTranscriptEvent
    | GeminiInterruptedEvent
    | GeminiAssistantMetaTextEvent
    | GeminiAssistantAudioEvent
    | GeminiTurnCompleteEvent
)


@dataclass(slots=True)
class GeminiLiveReceiveAdapter:
    session: GeminiReceiveSession

    async def receive_events(self) -> AsyncIterator[GeminiLiveReceiveEvent]:
        async for message in self.session.receive():
            setup_complete = getattr(message, "setup_complete", None)
            if setup_complete:
                yield GeminiLiveSetupCompleteEvent(
                    session_id=(getattr(setup_complete, "session_id", None) or None)
                )

            content = getattr(message, "server_content", None)
            if not content:
                continue

            input_transcription = getattr(content, "input_transcription", None)
            if input_transcription and getattr(input_transcription, "text", None):
                yield GeminiInputTranscriptEvent(
                    text=input_transcription.text,
                    final=bool(getattr(input_transcription, "finished", False)),
                )

            output_transcription = getattr(content, "output_transcription", None)
            if output_transcription and getattr(output_transcription, "text", None):
                yield GeminiOutputTranscriptEvent(
                    text=output_transcription.text,
                    final=bool(getattr(output_transcription, "finished", False)),
                )

            if getattr(content, "interrupted", False):
                yield GeminiInterruptedEvent()

            model_turn = getattr(content, "model_turn", None)
            parts = getattr(model_turn, "parts", None) if model_turn else None
            if parts:
                for part in parts:
                    if getattr(part, "text", None):
                        yield GeminiAssistantMetaTextEvent(text=part.text)
                        continue

                    inline = getattr(part, "inline_data", None)
                    data = getattr(inline, "data", None) if inline else None
                    if not data:
                        continue

                    pcm_bytes = (
                        base64.b64decode(data.encode("ascii"), validate=False)
                        if isinstance(data, str)
                        else bytes(data)
                    )
                    yield GeminiAssistantAudioEvent(
                        pcm_bytes=pcm_bytes,
                        mime_type=getattr(inline, "mime_type", None),
                    )

            if getattr(content, "turn_complete", False):
                turn_complete_reason = getattr(content, "turn_complete_reason", None)
                reason_value = getattr(turn_complete_reason, "value", None) if turn_complete_reason else None
                yield GeminiTurnCompleteEvent(reason=str(reason_value or "unknown"))
