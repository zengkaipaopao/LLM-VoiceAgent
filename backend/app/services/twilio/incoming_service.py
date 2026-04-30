import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.exceptions import BusinessException
from app.services.live_gateway import provider_available, resolve_live_provider
from app.services.twilio.active_inbound_profile import (
    _get_active_inbound_profile_for_number,
    _set_active_inbound_profile_for_number,
)
from app.services.twilio.incoming_route_runtime import (
    OFFICIAL_DEMO_TEMPLATE_CODE,
    build_official_demo_runtime,
    is_official_conversational_agents_route,
    is_official_demo_route,
    resolve_twilio_incoming_prompt_code,
)
from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_gemini_live_voice_name,
    _normalize_prompt_code_token,
    _normalize_twilio_voice_route,
    _normalize_voice_engine,
    _normalize_voice_name_token,
    _resolve_twilio_inbound_voice_route,
)
from app.services.twilio.official_conversational_agents import (
    build_official_conversational_agents_config,
    build_official_conversational_agents_stream_parameters,
)
from app.services.twilio.pending_overrides import (
    _consume_pending_inbound_override_for_number,
    _set_pending_inbound_override_for_number,
)
from app.services.twilio.prompt_runtime_helpers import (
    _require_opening_sentence,
    _resolve_gemini_live_model,
    _resolve_prompt_runtime,
)
from app.services.twilio.twiml_builders import _build_twilio_media_stream_twiml
from app.services.twilio_voice_agent_service import twilio_voice_agent_service
from app.services.twilio_webcall_service import TwilioWebCallService

logger = logging.getLogger(__name__)

VALID_INBOUND_VOICE_ROUTES = {
    "gather",
    "media_stream_live",
    "official_demo_live",
    "official_conversational_agents",
}


@dataclass(frozen=True)
class TwilioTwiMLAppPayload:
    to_number: Optional[str] = None
    from_number: Optional[str] = None
    call_sid: Optional[str] = None
    prompt_code: Optional[str] = None
    voice_route: Optional[str] = None
    voice_engine: Optional[str] = None
    voice_name: Optional[str] = None


@dataclass(frozen=True)
class TwilioIncomingVoicePayload:
    identity: str
    prompt_code: Optional[str] = None
    mode: Optional[str] = None
    voice_route: Optional[str] = None
    voice_engine: Optional[str] = None
    voice_name: Optional[str] = None
    to_number: Optional[str] = None
    from_number: Optional[str] = None
    call_sid: Optional[str] = None


@dataclass(frozen=True)
class TwilioAgentTurnPayload:
    prompt_code: Optional[str] = None
    call_sid: Optional[str] = None
    to_number: Optional[str] = None
    speech_result: Optional[str] = None


class TwilioIncomingService:
    """Application service for Twilio inbound voice TwiML decisions."""

    def __init__(
        self,
        *,
        webcall_service: TwilioWebCallService | None = None,
    ) -> None:
        self.webcall_service = webcall_service or TwilioWebCallService()
        self.voice_agent_service = twilio_voice_agent_service

    async def build_twiml_app_voice_response(self, payload: TwilioTwiMLAppPayload) -> str:
        active_profile = await _set_active_inbound_profile_for_number(
            number=payload.to_number,
            prompt_code=payload.prompt_code,
            voice_route=payload.voice_route,
            voice_engine=payload.voice_engine,
            voice_name=payload.voice_name,
        )
        queued_override = await _set_pending_inbound_override_for_number(
            number=payload.to_number,
            prompt_code=payload.prompt_code,
            voice_route=payload.voice_route,
            voice_engine=payload.voice_engine,
            voice_name=payload.voice_name,
        )
        if queued_override:
            logger.info(
                (
                    "Queued pending inbound override for outbound->inbound bridge. "
                    "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
                ),
                _normalize_e164_number(payload.to_number),
                _normalize_prompt_code_token(payload.prompt_code),
                _normalize_twilio_voice_route(payload.voice_route),
                _normalize_voice_engine(payload.voice_engine),
                _normalize_voice_name_token(payload.voice_name),
            )
        if active_profile:
            logger.info(
                (
                    "Updated active inbound profile from TwiML app webhook. "
                    "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
                ),
                _normalize_e164_number(payload.to_number),
                active_profile.get("prompt_code"),
                active_profile.get("voice_route"),
                active_profile.get("voice_engine"),
                active_profile.get("voice_name"),
            )

        xml = self.webcall_service.build_outbound_twiml(payload.to_number or "")
        logger.info(
            (
                "Twilio TwiML app webhook called. "
                "CallSid=%s From=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
            ),
            payload.call_sid,
            payload.from_number,
            payload.to_number,
            payload.prompt_code,
            payload.voice_route,
            payload.voice_engine,
            payload.voice_name,
        )
        return xml

    async def build_incoming_voice_response(
        self,
        *,
        request: Request,
        db: AsyncSession,
        payload: TwilioIncomingVoicePayload,
    ) -> str:
        pending_override = await _consume_pending_inbound_override_for_number(payload.to_number)
        active_profile = await _get_active_inbound_profile_for_number(payload.to_number)
        pending_prompt = pending_override.get("prompt_code") if pending_override else None
        pending_route = pending_override.get("voice_route") if pending_override else None
        pending_engine = pending_override.get("voice_engine") if pending_override else None
        pending_voice_name = pending_override.get("voice_name") if pending_override else None
        active_prompt = active_profile.get("prompt_code") if active_profile else None
        active_route = active_profile.get("voice_route") if active_profile else None
        active_engine = active_profile.get("voice_engine") if active_profile else None
        active_voice_name = active_profile.get("voice_name") if active_profile else None

        mode_value = (payload.mode or settings.twilio_incoming_default_mode or "agent").strip().lower()
        effective_route = payload.voice_route or pending_route or active_route
        effective_engine = payload.voice_engine or pending_engine or active_engine
        route_value = _resolve_twilio_inbound_voice_route(
            voice_route=effective_route,
            voice_engine=effective_engine,
        )
        effective_prompt = payload.prompt_code or pending_prompt or active_prompt
        resolved_prompt_code = await self._resolve_prompt_code(
            db=db,
            route_value=route_value,
            effective_prompt=effective_prompt,
            to_number=payload.to_number,
        )

        if route_value not in VALID_INBOUND_VOICE_ROUTES:
            logger.warning(
                "Twilio inbound voice route invalid. route=%s engine=%s call_sid=%s to=%s",
                effective_route,
                effective_engine,
                payload.call_sid,
                payload.to_number,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text="音声エンジン設定が不正です。設定を確認してください。",
                language=settings.twilio_agent_language,
            )

        if mode_value == "agent":
            xml = await self._build_agent_mode_twiml(
                request=request,
                db=db,
                payload=payload,
                route_value=route_value,
                resolved_prompt_code=resolved_prompt_code,
                pending_voice_name=pending_voice_name,
                active_voice_name=active_voice_name,
            )
        else:
            xml = self.webcall_service.build_incoming_to_client_twiml(
                payload.identity,
                prompt_code=resolved_prompt_code,
            )

        self._log_incoming_voice_result(
            payload=payload,
            mode_value=mode_value,
            route_value=route_value,
            effective_engine=effective_engine,
            resolved_prompt_code=resolved_prompt_code,
            pending_override=pending_override,
            active_profile=active_profile,
            pending_prompt=pending_prompt,
            pending_route=pending_route,
            pending_engine=pending_engine,
            pending_voice_name=pending_voice_name,
            active_prompt=active_prompt,
            active_route=active_route,
            active_engine=active_engine,
            active_voice_name=active_voice_name,
        )
        return xml

    async def build_agent_turn_response(
        self,
        *,
        request: Request,
        db: AsyncSession,
        payload: TwilioAgentTurnPayload,
    ) -> str:
        call_sid = (payload.call_sid or "").strip() or "unknown-call"
        resolved_prompt_code = self.webcall_service.resolve_incoming_prompt_code(
            prompt_code=payload.prompt_code,
            to_number=payload.to_number,
        )
        turn_url = str(request.url_for("twilio_voice_agent_turn"))
        action_url = self.voice_agent_service.build_turn_action_url(turn_url, resolved_prompt_code)
        user_text = (payload.speech_result or "").strip()

        if not user_text:
            return self.voice_agent_service.build_gather_twiml(
                say_text=self.voice_agent_service.retry_text(),
                action_url=action_url,
                language=settings.twilio_agent_language,
            )

        if self.voice_agent_service.is_end_intent(user_text):
            await self.voice_agent_service.clear_session(call_sid)
            return self.voice_agent_service.build_hangup_twiml(
                say_text=self.voice_agent_service.closing_text(),
                language=settings.twilio_agent_language,
            )

        try:
            reply = await self.voice_agent_service.generate_reply(
                db=db,
                call_sid=call_sid,
                prompt_code=resolved_prompt_code,
                user_text=user_text,
            )
        except BusinessException as exc:
            logger.warning(
                "Twilio gather turn prompt configuration invalid. call_sid=%s prompt=%s error=%s",
                call_sid,
                resolved_prompt_code,
                exc,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
                language=settings.twilio_agent_language,
            )

        return self.voice_agent_service.build_gather_twiml(
            say_text=reply,
            action_url=action_url,
            language=settings.twilio_agent_language,
        )

    async def _resolve_prompt_code(
        self,
        *,
        db: AsyncSession,
        route_value: str | None,
        effective_prompt: str | None,
        to_number: str | None,
    ) -> str | None:
        if is_official_demo_route(route_value):
            return OFFICIAL_DEMO_TEMPLATE_CODE
        return await resolve_twilio_incoming_prompt_code(
            db=db,
            prompt_code=effective_prompt,
            to_number=to_number,
        )

    async def _build_agent_mode_twiml(
        self,
        *,
        request: Request,
        db: AsyncSession,
        payload: TwilioIncomingVoicePayload,
        route_value: str,
        resolved_prompt_code: str | None,
        pending_voice_name: str | None,
        active_voice_name: str | None,
    ) -> str:
        if is_official_conversational_agents_route(route_value):
            return self._build_official_conversational_agents_twiml(
                request=request,
                payload=payload,
                route_value=route_value,
            )
        if route_value in {"media_stream_live", "official_demo_live"}:
            return await self._build_media_stream_live_twiml(
                request=request,
                db=db,
                payload=payload,
                route_value=route_value,
                resolved_prompt_code=resolved_prompt_code,
                pending_voice_name=pending_voice_name,
                active_voice_name=active_voice_name,
            )
        return await self._build_gather_agent_twiml(
            request=request,
            db=db,
            payload=payload,
            resolved_prompt_code=resolved_prompt_code,
        )

    def _build_official_conversational_agents_twiml(
        self,
        *,
        request: Request,
        payload: TwilioIncomingVoicePayload,
        route_value: str,
    ) -> str:
        try:
            official_ca_config = build_official_conversational_agents_config()
        except ValueError as exc:
            logger.warning(
                "Twilio inbound official Conversational Agents configuration invalid. error=%s",
                exc,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text=(
                    "官方 Conversational Agents 基线未正确配置。"
                    "请检查后端 TWILIO_OFFICIAL_CA_* 配置后重试。"
                ),
                language=settings.twilio_agent_language,
            )

        extra_parameters = build_official_conversational_agents_stream_parameters(
            official_ca_config
        )
        if official_ca_config.kickstart_text:
            extra_parameters["ca_kickstart_text"] = official_ca_config.kickstart_text
        return _build_twilio_media_stream_twiml(
            request=request,
            prompt_code=OFFICIAL_DEMO_TEMPLATE_CODE,
            from_number=payload.from_number,
            to_number=payload.to_number,
            voice_name=None,
            route_name=route_value,
            websocket_endpoint_name="twilio_voice_official_conversational_agents_stream",
            extra_parameters=extra_parameters,
        )

    async def _build_media_stream_live_twiml(
        self,
        *,
        request: Request,
        db: AsyncSession,
        payload: TwilioIncomingVoicePayload,
        route_value: str,
        resolved_prompt_code: str | None,
        pending_voice_name: str | None,
        active_voice_name: str | None,
    ) -> str:
        try:
            if is_official_demo_route(route_value):
                runtime = build_official_demo_runtime()
            else:
                runtime = await _resolve_prompt_runtime(
                    db=db,
                    prompt_code=resolved_prompt_code,
                    model_capability="live",
                )
        except BusinessException as exc:
            logger.warning(
                "Twilio inbound media stream prompt configuration invalid. prompt=%s error=%s",
                resolved_prompt_code,
                exc,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text=(
                    "当前电话 Prompt 或官方基线 Demo 配置无效。"
                    "请检查 Prompt 管理或官方 Demo 环境变量后重试。"
                ),
                language=settings.twilio_agent_language,
            )

        try:
            selected_model = _resolve_gemini_live_model(runtime.llm_model)
        except ValueError as exc:
            logger.warning(
                "Twilio inbound prompt model incompatible with media stream live. prompt=%s error=%s",
                resolved_prompt_code,
                exc,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text=(
                    "当前 Prompt 模型不能用于 Twilio Media Streams。"
                    "请切换到 Gemini Live / Native Audio 模型后再测试。"
                ),
                language=settings.twilio_agent_language,
            )

        selected_provider = resolve_live_provider(runtime.llm_provider, selected_model)
        available, reason = provider_available(selected_provider)
        if selected_provider != "gemini" or not available:
            logger.warning(
                "Twilio inbound media stream provider unavailable. provider=%s prompt=%s reason=%s",
                selected_provider,
                resolved_prompt_code,
                reason,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text="当前电话音频桥接不可用。请检查 Gemini Live 配置后重试。",
                language=settings.twilio_agent_language,
            )

        selected_voice_override = _normalize_voice_name_token(
            payload.voice_name or pending_voice_name or active_voice_name
        )
        requested_live_voice = selected_voice_override or runtime.voice_id
        resolved_live_voice = _normalize_gemini_live_voice_name(
            requested_live_voice,
            voice_provider=runtime.voice_provider,
            default_voice=settings.default_live_voice or "Aoede",
        )
        if (requested_live_voice or "").strip() and resolved_live_voice != requested_live_voice:
            logger.info(
                "Normalized Twilio media stream voice for Gemini Live. requested=%s resolved=%s prompt=%s provider=%s",
                requested_live_voice,
                resolved_live_voice,
                runtime.template_code,
                runtime.voice_provider,
            )
        return _build_twilio_media_stream_twiml(
            request=request,
            prompt_code=runtime.template_code,
            from_number=payload.from_number,
            to_number=payload.to_number,
            voice_name=resolved_live_voice,
            route_name=route_value,
        )

    async def _build_gather_agent_twiml(
        self,
        *,
        request: Request,
        db: AsyncSession,
        payload: TwilioIncomingVoicePayload,
        resolved_prompt_code: str | None,
    ) -> str:
        try:
            runtime = await _resolve_prompt_runtime(
                db=db,
                prompt_code=resolved_prompt_code,
                model_capability="generate",
            )
            opening_text = _require_opening_sentence(
                system_instruction=runtime.system_instruction,
                template_code=runtime.template_code,
            )
        except BusinessException as exc:
            logger.warning(
                "Twilio gather prompt configuration invalid. prompt=%s error=%s",
                resolved_prompt_code,
                exc,
            )
            return self.voice_agent_service.build_hangup_twiml(
                say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
                language=settings.twilio_agent_language,
            )

        turn_url = str(request.url_for("twilio_voice_agent_turn"))
        action_url = self.voice_agent_service.build_turn_action_url(turn_url, runtime.template_code)
        call_sid = (payload.call_sid or "").strip()
        if call_sid:
            await self.voice_agent_service.ensure_session(
                db=db,
                call_sid=call_sid,
                prompt_code=runtime.template_code,
            )
        return self.voice_agent_service.build_gather_twiml(
            say_text=opening_text,
            action_url=action_url,
            language=settings.twilio_agent_language,
        )

    def _log_incoming_voice_result(
        self,
        *,
        payload: TwilioIncomingVoicePayload,
        mode_value: str,
        route_value: str | None,
        effective_engine: str | None,
        resolved_prompt_code: str | None,
        pending_override: dict[str, str | None] | None,
        active_profile: dict[str, str | None] | None,
        pending_prompt: str | None,
        pending_route: str | None,
        pending_engine: str | None,
        pending_voice_name: str | None,
        active_prompt: str | None,
        active_route: str | None,
        active_engine: str | None,
        active_voice_name: str | None,
    ) -> None:
        logger.info(
            (
                "Twilio inbound webhook called. "
                "CallSid=%s From=%s To=%s mode=%s route=%s engine=%s identity=%s prompt_code=%s"
            ),
            payload.call_sid,
            payload.from_number,
            payload.to_number,
            mode_value,
            route_value,
            effective_engine,
            payload.identity,
            resolved_prompt_code,
        )
        explicit_overrides = any(
            [
                (payload.prompt_code or "").strip(),
                (payload.voice_route or "").strip(),
                (payload.voice_engine or "").strip(),
                (payload.voice_name or "").strip(),
            ]
        )
        if explicit_overrides:
            return
        if pending_override:
            logger.info(
                (
                    "Applied pending inbound override for inbound call. "
                    "CallSid=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
                ),
                payload.call_sid,
                _normalize_e164_number(payload.to_number),
                pending_prompt,
                pending_route,
                pending_engine,
                pending_voice_name,
            )
        elif active_profile:
            logger.info(
                (
                    "Applied active inbound profile for inbound call. "
                    "CallSid=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
                ),
                payload.call_sid,
                _normalize_e164_number(payload.to_number),
                active_prompt,
                active_route,
                active_engine,
                active_voice_name,
            )
