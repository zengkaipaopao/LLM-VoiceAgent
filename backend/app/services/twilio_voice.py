from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Iterable, Mapping

import httpx
from fastapi import HTTPException
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from app.core.config import settings
from app.core.utils import split_models
from app.schemas.appointments import AppointmentCreateRequest
from app.schemas.chat import ChatMessage, ChatRequest
from app.schemas.prompts import PromptTemplate
from app.services.appointment_service import appointment_service
from app.services.chat_service import chat_service
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)


FINAL_CONFIRMATION_PHRASES = ("ご予約内容を受付いたしました", "ご利用ありがとうございます")
JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*({[\s\S]+?})\s*```", re.IGNORECASE)
EXTRA_REQUEST_NONE_KEYWORDS = [
    "なし",
    "追加要望なし",
    "追加要望はありません",
    "特にありません",
    "特にない",
    "ありません",
    "ない",
    "no",
    "none",
]


@dataclass
class ParsedAppointment:
    operation: str
    timestamp: str
    caller_name: str
    company: str
    appointment: str
    category: str
    amount: str
    address: str
    summary: str
    extra_request: str


class TwilioVoiceService:
    """Twilio Voice helper for inbound/outbound tests with basic appointment logging.

    The class now keeps an in-memory transcript per CallSid, extracts JSON payloads that
    follow the `logChatToSheet` contract, and auto-creates appointment records when it
    detects a closing phrase or when the call ends unexpectedly.
    """

    _api_base = "https://api.twilio.com/2010-04-01"

    def __init__(self) -> None:
        self._account_sid = settings.twilio_account_sid or ""
        self._auth_token = settings.twilio_auth_token or ""
        self._default_from = settings.twilio_phone_number or ""
        self._twiml_app_sid = settings.twilio_twiml_app_sid
        self._prompt_id = settings.twilio_prompt_id or "prompt_1"
        self._prompt_cache: dict[str, PromptTemplate] = {}
        self._sessions: dict[str, list[ChatMessage]] = {}
        self._session_prompts: dict[str, str] = {}
        self._session_models: dict[str, str] = {}
        self._openai_models = set(split_models(settings.openai_models))
        self._chat_model_override = settings.twilio_chat_model_id
        self._session_lock = threading.Lock()
        self._transcripts: dict[str, list[dict[str, str]]] = {}
        self._parsed_records: dict[str, ParsedAppointment] = {}
        self._finalized_sessions: set[str] = set()

    def _require_credentials(self) -> None:
        if not (self._account_sid and self._auth_token and self._default_from):
            raise HTTPException(status_code=503, detail="未配置 Twilio 账号或号码。")

    def validate_signature(
        self,
        url: str,
        params: Iterable[tuple[str, str]],
        signature: str | None,
    ) -> None:
        """Validate X-Twilio-Signature header to ensure webhook authenticity."""
        if not self._auth_token:
            logger.warning("Twilio auth token not configured, skipping signature validation.")
            return
        if not signature:
            raise HTTPException(status_code=403, detail="缺少 Twilio Signature。")

        grouped: dict[str, list[str]] = {}
        for key, value in params:
            grouped.setdefault(key, []).append(value)
        sorted_payload = url + "".join(
            f"{key}{value}"
            for key in sorted(grouped.keys())
            for value in grouped[key]
        )
        expected = base64.b64encode(
            hmac.new(
                self._auth_token.encode("utf-8"),
                sorted_payload.encode("utf-8"),
                hashlib.sha1,
            ).digest(),
        ).decode("utf-8")
        if not hmac.compare_digest(expected, signature):
            logger.warning("Twilio signature mismatch")
            raise HTTPException(status_code=403, detail="Twilio Signature 无效。")

    async def build_twiml(self, payload: Mapping[str, str]) -> str:
        """Route outbound to PSTN when `To` is provided, otherwise start AI dialogue."""
        target = payload.get("To")
        if target and self._default_from and target != self._default_from:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response>"
                f'<Dial callerId="{self._default_from}">'
                f"<Number>{target}</Number>"
                "</Dial>"
                "</Response>"
            )
        return await self._handle_ai_dialogue(payload)

    async def place_call(self, to: str, *, url: str | None = None) -> str:
        """Trigger an outbound test call via Twilio's REST API."""
        self._require_credentials()
        request_url = f"{self._api_base}/Accounts/{self._account_sid}/Calls.json"
        payload = {
            "To": to,
            "From": self._default_from,
        }
        if self._twiml_app_sid:
            payload["ApplicationSid"] = self._twiml_app_sid
        elif url:
            payload["Url"] = url
        else:
            raise HTTPException(status_code=400, detail="未指定 TwiML App 或回调 URL。")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                request_url,
                data=payload,
                auth=(self._account_sid, self._auth_token),
                timeout=15,
            )
        if response.is_error:
            logger.error("Twilio call create failed: %s", response.text)
            raise HTTPException(status_code=502, detail="Twilio 呼叫创建失败。")
        return response.json().get("sid", "")

    def generate_client_token(self, identity: str) -> str:
        """Issue a Voice SDK token so the browser can place calls without PSTN."""
        api_key = settings.twilio_api_key_sid
        api_secret = settings.twilio_api_key_secret
        if not (
            api_key
            and api_secret
            and self._account_sid
            and self._twiml_app_sid
        ):
            raise HTTPException(status_code=503, detail="未配置 Twilio API Key 或 TwiML App。")
        token = AccessToken(
            self._account_sid,
            api_key,
            api_secret,
            identity=identity,
        )
        voice_grant = VoiceGrant(outgoing_application_sid=self._twiml_app_sid)
        voice_grant.incoming_allow = True
        token.add_grant(voice_grant)
        jwt = token.to_jwt()
        return jwt.decode("utf-8") if isinstance(jwt, bytes) else jwt

    async def _handle_ai_dialogue(self, payload: Mapping[str, str]) -> str:
        call_sid = payload.get("CallSid")
        if not call_sid:
            return self._say_once("システムエラーが発生しました。しばらくしてからお掛け直しください。")

        prompt_from_payload = payload.get("PromptId")
        status = (payload.get("CallStatus") or "").lower()
        if status in {"completed", "canceled", "busy", "failed", "no-answer"}:
            await self._finalize_appointment(call_sid, reason="hangup")
            self._cleanup_session(call_sid)
            return '<?xml version="1.0" encoding="UTF-8"?><Response/>'

        prompt_id = prompt_from_payload or self._session_prompts.get(call_sid) or self._prompt_id
        prompt = self._get_prompt(prompt_id)
        self._transcripts.setdefault(call_sid, [])
        with self._session_lock:
            session = self._sessions.get(call_sid)
            active_model = self._session_models.get(call_sid)
        speech_text = (payload.get("SpeechResult") or "").strip()

        if not session:
            session = [
                ChatMessage(
                    role="system",
                    content=prompt.instructions or prompt.system_prompt or "You are a polite Japanese receptionist.",
                )
            ]
            with self._session_lock:
                self._sessions[call_sid] = session
                self._session_prompts[call_sid] = prompt_id
                resolved_model = self._resolve_model_id(prompt.model_id)
                self._session_models[call_sid] = resolved_model
            session.append(ChatMessage(role="user", content="新しい電話が接続されました。最初の挨拶から会話を開始してください。"))
            target_model = self._session_models[call_sid]
            reply = await self._generate_reply(target_model, session)
            session.append(ChatMessage(role="assistant", content=reply))
            self._append_transcript(call_sid, "assistant", reply)
            self._maybe_capture_appointment(call_sid, reply)
            if self._contains_closing_phrase(reply):
                await self._finalize_appointment(call_sid, reason="closing")
            return self._reply_with_gather(reply)

        if not speech_text:
            return self._reply_with_gather("恐れ入りますが、もう一度ゆっくりお話しいただけますか？")

        session.append(ChatMessage(role="user", content=speech_text))
        self._append_transcript(call_sid, "user", speech_text)
        target_model = active_model or self._resolve_model_id(prompt.model_id)
        with self._session_lock:
            self._session_models[call_sid] = target_model
        reply = await self._generate_reply(target_model, session)
        session.append(ChatMessage(role="assistant", content=reply))
        self._append_transcript(call_sid, "assistant", reply)
        self._maybe_capture_appointment(call_sid, reply)
        if self._contains_closing_phrase(reply):
            await self._finalize_appointment(call_sid, reason="closing")
        return self._reply_with_gather(reply)

    def _get_prompt(self, prompt_id: str) -> PromptTemplate:
        if not prompt_id:
            raise HTTPException(status_code=503, detail="未配置语音用 Prompt。")
        cached = self._prompt_cache.get(prompt_id)
        if cached is not None:
            return cached
        try:
            prompt = prompt_service.get_prompt(prompt_id)
        except KeyError as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail=f"未找到 Prompt {prompt_id}") from exc
        self._prompt_cache[prompt_id] = prompt
        return prompt

    def _resolve_model_id(self, prompt_model_id: str | None) -> str:
        candidate = (prompt_model_id or "").strip()
        if candidate and (not self._openai_models or candidate in self._openai_models):
            return candidate
        override = (self._chat_model_override or "").strip()
        if override:
            return override
        realtime_default = (settings.openai_realtime_model or "").strip()
        if realtime_default and (not self._openai_models or realtime_default in self._openai_models):
            return realtime_default
        if self._openai_models:
            return next(iter(self._openai_models))
        raise HTTPException(status_code=503, detail="未配置可用于 Twilio 的聊天模型。")

    async def _generate_reply(self, model_id: str, messages: list[ChatMessage]) -> str:
        request = ChatRequest(model_id=model_id, messages=messages[-10:])
        response = await chat_service.chat(request)
        text = (response.reply or "").strip()
        if not text:
            text = "失礼いたしました。もう一度ご説明いただけますでしょうか。"
        return text

    def _append_transcript(self, call_sid: str, role: str, text: str) -> None:
        if not text:
            return
        entry = {
            "role": role,
            "text": text,
            "ts": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._transcripts.setdefault(call_sid, []).append(entry)

    def _maybe_capture_appointment(self, call_sid: str, text: str) -> bool:
        parsed = self._extract_appointment_from_text(text)
        if not parsed:
            return False
        self._parsed_records[call_sid] = parsed
        return True

    def _contains_closing_phrase(self, text: str) -> bool:
        if not text:
            return False
        return all(phrase in text for phrase in FINAL_CONFIRMATION_PHRASES)

    def _extract_appointment_from_text(self, text: str) -> ParsedAppointment | None:
        if not text:
            return None
        json_str = self._extract_json_string(text)
        if not json_str:
            return None
        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        def pick(keys: list[str]) -> str:
            for key in keys:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        timestamp = pick(["timestamp", "time"]) or self._current_timestamp()
        caller = pick(["caller_name", "callerName", "name"])
        company = pick(["company", "company_name", "companyName"])
        appointment = pick(["appointment", "desired_time", "desiredTime"])
        category = pick(["category", "item"])
        amount = pick(["amount", "quantity"])
        address = pick(["address", "location"])
        summary = pick(["summary", "note"]) or "要約未設定"
        extra_request = self._normalize_extra_request(
            pick(["extra_request", "additional_request", "additionalRequest"])
        )
        if not all([caller, company, appointment, category, amount, address]):
            return None
        operation = self._normalize_operation(payload.get("operation") or payload.get("action"))
        return ParsedAppointment(
            operation=operation,
            timestamp=timestamp,
            caller_name=caller,
            company=company,
            appointment=appointment,
            category=category,
            amount=amount,
            address=address,
            summary=summary,
            extra_request=extra_request,
        )

    def _extract_json_string(self, text: str) -> str | None:
        match = JSON_BLOCK_PATTERN.search(text)
        if match:
            return match.group(1)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return text[start : end + 1]
        return None

    def _normalize_extra_request(self, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            return "なし"
        normalized = trimmed.replace(" ", "").lower()
        for keyword in EXTRA_REQUEST_NONE_KEYWORDS:
            if keyword.replace(" ", "").lower() in normalized:
                return "なし"
        return trimmed

    def _normalize_operation(self, value: str | None) -> str:
        if not value:
            return "create"
        normalized = value.lower()
        if "update" in normalized or "modify" in normalized or "変更" in normalized:
            return "update"
        if "delete" in normalized or "cancel" in normalized or "取消" in normalized:
            return "delete"
        return "create"

    def _current_timestamp(self) -> str:
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    async def _finalize_appointment(self, call_sid: str, reason: str) -> None:
        if call_sid in self._finalized_sessions:
            return
        parsed = self._parsed_records.get(call_sid)
        if not parsed:
            return
        raw_messages = self._serialize_transcript(call_sid)
        if not raw_messages:
            return
        payload = AppointmentCreateRequest(
            timestamp=parsed.timestamp or self._current_timestamp(),
            caller_name=parsed.caller_name,
            company=parsed.company,
            appointment=parsed.appointment,
            category=parsed.category,
            amount=parsed.amount,
            address=parsed.address,
            summary=parsed.summary or "要約未設定",
            extra_request=parsed.extra_request,
            raw_messages=raw_messages,
            operation=parsed.operation,  # type: ignore[arg-type]
        )
        try:
            await appointment_service.create_from_conversation(payload)
            self._finalized_sessions.add(call_sid)
            logger.info("Appointment record created for call %s via %s", call_sid, reason)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to create appointment for call %s: %s", call_sid, exc)

    def _serialize_transcript(self, call_sid: str) -> str:
        entries = self._transcripts.get(call_sid, [])
        if not entries:
            return ""
        return ", ".join(json.dumps(entry, ensure_ascii=False) for entry in entries)

    def _cleanup_session(self, call_sid: str) -> None:
        with self._session_lock:
            self._sessions.pop(call_sid, None)
            self._session_prompts.pop(call_sid, None)
            self._session_models.pop(call_sid, None)
        self._transcripts.pop(call_sid, None)
        self._parsed_records.pop(call_sid, None)
        self._finalized_sessions.discard(call_sid)

    def _reply_with_gather(self, text: str) -> str:
        language = settings.twilio_say_language or "ja-JP"
        voice = settings.twilio_say_voice or "Polly.Mizuki"
        safe_text = escape(text)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f'<Gather input="speech" speechTimeout="auto" action="/api/twilio/voice" method="POST" language="{language}">'
            f'<Say voice="{voice}" language="{language}">{safe_text}</Say>'
            "</Gather>"
            "</Response>"
        )

    @staticmethod
    def _say_once(text: str) -> str:
        safe = escape(text)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f'<Say language="ja-JP">{safe}</Say>'
            "</Response>"
        )


twilio_voice_service = TwilioVoiceService()
