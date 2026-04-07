"""
Twilio voice agent loop service.

Implements a speech-driven call loop for PSTN calls:
- Twilio <Gather input="speech"> transcribes caller utterance
- Backend calls LLM with prompt template context
- Twilio <Say> plays assistant reply and gathers next turn
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.live_gateway import infer_provider_from_model, normalize_provider
from app.services.prompt_service import PromptService
from app.services.voice_runtime import (
    VoiceProviderNotImplementedError,
    VoiceProviderUnavailableError,
    VoiceTurnEngineFactory,
    VoiceTurnRequest,
)

logger = logging.getLogger(__name__)


@dataclass
class TwilioVoiceSession:
    call_sid: str
    prompt_code: str
    system_prompt: str
    llm_provider: str
    llm_model: str
    temperature: float
    max_tokens: int
    history: list[dict[str, str]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TwilioVoiceAgentService:
    _OPENING_TEXT = (
        "いつもお世話になっております。光洲産業の自動受付AIです。"
        "本日はどのようなご用件でしょうか。"
    )
    _RETRY_TEXT = "恐れ入ります。うまく聞き取れませんでした。もう一度お願いいたします。"
    _FAILURE_TEXT = "申し訳ありません。現在応答を生成できません。少し時間をおいてお試しください。"
    _NO_API_KEY_TEXT = "現在AIの設定が未完了です。担当者に設定確認を依頼してください。"
    _PROVIDER_UNAVAILABLE_TEXT = (
        "現在AIエンジン設定を確認中です。少し時間をおいて再度お試しください。"
    )
    _PROVIDER_NOT_IMPLEMENTED_TEXT = "この対話エンジンは現在準備中です。別の設定でお試しください。"
    _CLOSING_TEXT = "お電話ありがとうございました。失礼いたします。"
    _END_KEYWORDS = ("終了", "終わり", "切ります", "切って", "以上です", "さようなら")
    _MAX_HISTORY_MESSAGES = 24
    _MAX_CONTEXT_MESSAGES = 12
    _SESSION_TTL = timedelta(hours=2)

    def __init__(self) -> None:
        self._sessions: dict[str, TwilioVoiceSession] = {}
        self._lock = asyncio.Lock()

    async def _prune_expired_sessions(self) -> None:
        cutoff = datetime.now(UTC) - self._SESSION_TTL
        stale_keys = [sid for sid, session in self._sessions.items() if session.updated_at < cutoff]
        for sid in stale_keys:
            self._sessions.pop(sid, None)

    async def ensure_session(
        self,
        *,
        db: AsyncSession,
        call_sid: str,
        prompt_code: str | None,
    ) -> TwilioVoiceSession:
        async with self._lock:
            await self._prune_expired_sessions()
            existing = self._sessions.get(call_sid)
            if existing and (not prompt_code or existing.prompt_code == prompt_code):
                existing.updated_at = datetime.now(UTC)
                return existing

        resolved_code = (
            prompt_code or settings.twilio_default_prompt_code or "general_appointment"
        ).strip()
        prompt_service = PromptService(db)
        template = await prompt_service.get_template(resolved_code)
        if not template and resolved_code != "general_appointment":
            template = await prompt_service.get_template("general_appointment")

        system_prompt = (
            template.system_prompt
            if template and template.system_prompt
            else (
                "あなたは日本語のコールセンター受付AIです。"
                "丁寧に1項目ずつ確認し、推測せず、自然な会話で応答してください。"
            )
        )
        llm_provider = template.llm_provider if template and template.llm_provider else None
        llm_model = (
            template.llm_model
            if template and template.llm_model
            else settings.default_llm_model
        )
        temperature = float(
            template.temperature
            if template and template.temperature is not None
            else settings.llm_temperature
        )
        max_tokens = int(
            template.max_tokens if template and template.max_tokens else settings.llm_max_tokens
        )
        llm_provider = self._resolve_provider(
            provider=llm_provider,
            model=llm_model,
        )

        session = TwilioVoiceSession(
            call_sid=call_sid,
            prompt_code=(template.code if template else resolved_code),
            system_prompt=system_prompt,
            llm_provider=llm_provider,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(
            "Twilio voice session bound. call_sid=%s prompt_code=%s provider=%s model=%s",
            call_sid,
            session.prompt_code,
            session.llm_provider,
            session.llm_model,
        )

        async with self._lock:
            self._sessions[call_sid] = session
        return session

    async def clear_session(self, call_sid: str) -> None:
        async with self._lock:
            self._sessions.pop((call_sid or "").strip(), None)

    @classmethod
    def is_end_intent(cls, user_text: str) -> bool:
        text = (user_text or "").strip()
        if not text:
            return False
        return any(keyword in text for keyword in cls._END_KEYWORDS)

    @staticmethod
    def sanitize_reply(text: str) -> str:
        if not text:
            return ""
        normalized = text.strip()

        # Cut hallucinated next-turn transcript.
        injected_user = re.search(r"(?im)(^|\n)\s*user\s*[:：]", normalized)
        if injected_user:
            normalized = normalized[: injected_user.start()].strip()

        # Remove speaker role labels.
        normalized = re.sub(r"(?im)^\s*(assistant|ai助手|助手)\s*[:：]\s*", "", normalized).strip()
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        return normalized

    async def generate_reply(
        self,
        *,
        db: AsyncSession,
        call_sid: str,
        prompt_code: str | None,
        user_text: str,
    ) -> str:
        session = await self.ensure_session(db=db, call_sid=call_sid, prompt_code=prompt_code)

        user_message = {"role": "user", "content": (user_text or "").strip()}
        session.history.append(user_message)

        if len(session.history) > self._MAX_HISTORY_MESSAGES:
            session.history = session.history[-self._MAX_HISTORY_MESSAGES :]

        context_messages = session.history[-self._MAX_CONTEXT_MESSAGES :]
        logger.info(
            "Twilio voice turn. call_sid=%s prompt_code=%s provider=%s model=%s user_chars=%s",
            call_sid,
            session.prompt_code,
            session.llm_provider,
            session.llm_model,
            len(user_text or ""),
        )

        try:
            request = VoiceTurnRequest(
                provider=session.llm_provider,
                model=session.llm_model,
                system_prompt=session.system_prompt,
                messages=context_messages,
                temperature=session.temperature,
                max_tokens=session.max_tokens,
            )
            raw_reply = await self._generate_with_provider_fallback(request)
            if raw_reply == self._NO_API_KEY_TEXT:
                reply = raw_reply
            else:
                reply = self.sanitize_reply(raw_reply) or self._FAILURE_TEXT
        except VoiceProviderUnavailableError as exc:
            logger.warning(
                "Voice provider unavailable for call_sid=%s: %s",
                call_sid,
                exc,
            )
            reply = self._PROVIDER_UNAVAILABLE_TEXT
        except VoiceProviderNotImplementedError as exc:
            logger.warning(
                "Voice provider not implemented for call_sid=%s: %s",
                call_sid,
                exc,
            )
            reply = self._PROVIDER_NOT_IMPLEMENTED_TEXT
        except Exception as exc:
            logger.exception("Voice turn generation failed for call_sid=%s: %s", call_sid, exc)
            reply = self._FAILURE_TEXT

        session.history.append({"role": "assistant", "content": reply})
        if len(session.history) > self._MAX_HISTORY_MESSAGES:
            session.history = session.history[-self._MAX_HISTORY_MESSAGES :]
        session.updated_at = datetime.now(UTC)
        return reply

    async def _generate_with_provider_fallback(self, request: VoiceTurnRequest) -> str:
        primary_provider = self._resolve_provider(
            provider=request.provider,
            model=request.model,
        )
        fallback_provider = (settings.default_llm_provider or "gemini").strip().lower()
        strict_mode = bool(settings.twilio_strict_template_provider)
        attempted: list[str] = []

        providers = [primary_provider]
        if not strict_mode:
            normalized_fallback = self._resolve_provider(
                provider=fallback_provider,
                model=request.model,
            )
            if normalized_fallback and normalized_fallback not in providers:
                providers.append(normalized_fallback)

        for provider in providers:
            if not provider or provider in attempted:
                continue
            attempted.append(provider)
            engine = VoiceTurnEngineFactory.create(provider)
            available, reason = engine.is_available()
            if not available:
                logger.warning(
                    "Voice provider unavailable. provider=%s reason=%s",
                    provider,
                    reason,
                )
                if strict_mode or provider == providers[-1]:
                    raise VoiceProviderUnavailableError(
                        reason or f"{provider} provider unavailable"
                    )
                continue

            try:
                model_for_turn = (
                    request.model
                    if provider == primary_provider
                    else self._fallback_model_for_provider(provider, request.model)
                )
                return await engine.generate_reply(
                    VoiceTurnRequest(
                        provider=provider,
                        model=model_for_turn,
                        system_prompt=request.system_prompt,
                        messages=request.messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                    )
                )
            except VoiceProviderNotImplementedError:
                if strict_mode or provider == providers[-1]:
                    raise
                continue
            except VoiceProviderUnavailableError:
                if strict_mode or provider == providers[-1]:
                    raise
                continue

        if strict_mode and self._is_provider_key_missing(primary_provider):
            return self._NO_API_KEY_TEXT

        if not strict_mode and attempted and all(
            self._is_provider_key_missing(provider) for provider in attempted
        ):
            return self._NO_API_KEY_TEXT

        raise VoiceProviderUnavailableError(
            f"All configured providers unavailable. attempted={','.join(attempted) or 'none'}"
        )

    @staticmethod
    def _resolve_provider(*, provider: str | None, model: str | None) -> str:
        token = (provider or "").strip()
        if token:
            normalized = normalize_provider(token)
            if normalized in VoiceTurnEngineFactory.supported_providers():
                return normalized

        inferred = infer_provider_from_model(model)
        if inferred:
            return inferred

        fallback = normalize_provider(settings.default_llm_provider)
        if fallback in VoiceTurnEngineFactory.supported_providers():
            return fallback
        return "gemini"

    @staticmethod
    def _model_matches_provider(model: str, provider: str) -> bool:
        token = (model or "").strip().lower()
        current = normalize_provider(provider)
        if not token:
            return False
        if current == "gemini":
            return "gemini" in token
        if current == "openai":
            return token.startswith("gpt-") or "openai" in token
        return False

    @classmethod
    def _fallback_model_for_provider(cls, provider: str, requested_model: str | None) -> str:
        model = (requested_model or "").strip()
        if model and cls._model_matches_provider(model, provider):
            return model

        default_model = (settings.default_llm_model or "").strip()
        if default_model and cls._model_matches_provider(default_model, provider):
            return default_model

        if normalize_provider(provider) == "openai":
            return "gpt-4o-mini"
        return "gemini-2.0-flash"

    @staticmethod
    def _is_provider_key_missing(provider: str) -> bool:
        normalized = normalize_provider(provider)
        if normalized == "gemini":
            return not (settings.google_api_key or "").strip()
        if normalized == "openai":
            return not (settings.openai_api_key or "").strip()
        return False

    @classmethod
    def opening_text(cls) -> str:
        return cls._OPENING_TEXT

    @classmethod
    def retry_text(cls) -> str:
        return cls._RETRY_TEXT

    @classmethod
    def closing_text(cls) -> str:
        return cls._CLOSING_TEXT

    @staticmethod
    def build_turn_action_url(base_url: str, prompt_code: str | None) -> str:
        code = (prompt_code or "").strip()
        if not code:
            return base_url
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{urlencode({'prompt_code': code})}"

    @staticmethod
    def build_gather_twiml(*, say_text: str, action_url: str, language: str) -> str:
        safe_text = html.escape(say_text or "")
        safe_action = html.escape(action_url or "")
        safe_language = html.escape(language or "ja-JP")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Gather input=\"speech\" language=\"{safe_language}\" "
            "speechTimeout=\"auto\" timeout=\"5\" "
            f"action=\"{safe_action}\" method=\"POST\">"
            f"<Say language=\"{safe_language}\">{safe_text}</Say>"
            "</Gather>"
            f"<Redirect method=\"POST\">{safe_action}</Redirect>"
            "</Response>"
        )

    @staticmethod
    def build_hangup_twiml(*, say_text: str, language: str) -> str:
        safe_text = html.escape(say_text or "")
        safe_language = html.escape(language or "ja-JP")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f"<Say language=\"{safe_language}\">{safe_text}</Say>"
            "<Hangup/>"
            "</Response>"
        )


twilio_voice_agent_service = TwilioVoiceAgentService()
