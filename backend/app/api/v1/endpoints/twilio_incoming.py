import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.exceptions import BusinessException
from app.services.live_gateway import provider_available, resolve_live_provider
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
from app.services.twilio.webhook_verification import _verify_webhook_or_raise
from app.services.twilio_voice_agent_service import twilio_voice_agent_service
from app.services.twilio_webcall_service import TwilioWebCallService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/voice/twiml")
async def twiml_app_voice_webhook(
    request: Request,
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
    voice_route: Optional[str] = Form(None),
    voice_engine: Optional[str] = Form(None),
    voice_name: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    queued_override = await _set_pending_inbound_override_for_number(
        number=To,
        prompt_code=prompt_code,
        voice_route=voice_route,
        voice_engine=voice_engine,
        voice_name=voice_name,
    )
    if queued_override:
        logger.info(
            (
                "Queued pending inbound override for outbound->inbound bridge. "
                "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
            ),
            _normalize_e164_number(To),
            _normalize_prompt_code_token(prompt_code),
            _normalize_twilio_voice_route(voice_route),
            _normalize_voice_engine(voice_engine),
            _normalize_voice_name_token(voice_name),
        )
    xml = service.build_outbound_twiml(To or "")
    logger.info(
        (
            "Twilio TwiML app webhook called. "
            "CallSid=%s From=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
        ),
        CallSid,
        From,
        To,
        prompt_code,
        voice_route,
        voice_engine,
        voice_name,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/incoming")
async def incoming_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
    prompt_code: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    voice_route: Optional[str] = Query(
        default=None,
        description=(
            "Inbound AI voice route: gather or official_conversational_agents. "
            "Legacy aliases media_stream_live and official_demo_live are normalized "
            "to official_conversational_agents."
        ),
    ),
    voice_engine: Optional[str] = Query(
        default=None,
        description="Inbound AI voice engine: twilio or gemini.",
    ),
    voice_name: Optional[str] = Query(
        default=None,
        description="Optional Gemini Live voice override.",
    ),
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    pending_override = await _consume_pending_inbound_override_for_number(To)
    pending_prompt = pending_override.get("prompt_code") if pending_override else None
    pending_route = pending_override.get("voice_route") if pending_override else None
    pending_engine = pending_override.get("voice_engine") if pending_override else None
    pending_voice_name = pending_override.get("voice_name") if pending_override else None
    mode_value = ((mode or settings.twilio_incoming_default_mode or "agent").strip().lower())
    effective_route = voice_route or pending_route
    effective_engine = voice_engine or pending_engine
    route_value = _resolve_twilio_inbound_voice_route(
        voice_route=effective_route,
        voice_engine=effective_engine,
    )
    effective_prompt = prompt_code or pending_prompt
    resolved_prompt_code: str | None
    if is_official_demo_route(route_value):
        resolved_prompt_code = OFFICIAL_DEMO_TEMPLATE_CODE
    else:
        resolved_prompt_code = await resolve_twilio_incoming_prompt_code(
            db=db,
            prompt_code=effective_prompt,
            to_number=To,
        )
    xml: str
    if route_value not in {
        "gather",
        "media_stream_live",
        "official_demo_live",
        "official_conversational_agents",
    }:
        logger.warning(
            "Twilio inbound voice route invalid. route=%s engine=%s call_sid=%s to=%s",
            effective_route,
            effective_engine,
            CallSid,
            To,
        )
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text="音声エンジン設定が不正です。設定を確認してください。",
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    if mode_value == "agent":
        if is_official_conversational_agents_route(route_value):
            try:
                official_ca_config = build_official_conversational_agents_config()
            except ValueError as exc:
                logger.warning(
                    "Twilio inbound official Conversational Agents configuration invalid. error=%s",
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "官方 Conversational Agents 基线未正确配置。"
                        "请检查后端 TWILIO_OFFICIAL_CA_* 配置后重试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            extra_parameters = build_official_conversational_agents_stream_parameters(
                official_ca_config
            )
            if official_ca_config.kickstart_text:
                extra_parameters["ca_kickstart_text"] = official_ca_config.kickstart_text
            xml = _build_twilio_media_stream_twiml(
                request=request,
                prompt_code=OFFICIAL_DEMO_TEMPLATE_CODE,
                from_number=From,
                to_number=To,
                voice_name=None,
                route_name=route_value,
                websocket_endpoint_name="twilio_voice_official_conversational_agents_stream",
                extra_parameters=extra_parameters,
            )
        elif route_value in {"media_stream_live", "official_demo_live"}:
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
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "当前电话 Prompt 或官方基线 Demo 配置无效。"
                        "请检查 Prompt 管理或官方 Demo 环境变量后重试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")
            try:
                selected_model = _resolve_gemini_live_model(runtime.llm_model)
            except ValueError as exc:
                logger.warning(
                    "Twilio inbound prompt model incompatible with media stream live. prompt=%s error=%s",
                    resolved_prompt_code,
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "当前 Prompt 模型不能用于 Twilio Media Streams。"
                        "请切换到 Gemini Live / Native Audio 模型后再测试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            selected_provider = resolve_live_provider(runtime.llm_provider, selected_model)
            available, reason = provider_available(selected_provider)
            if selected_provider != "gemini" or not available:
                logger.warning(
                    "Twilio inbound media stream provider unavailable. provider=%s prompt=%s reason=%s",
                    selected_provider,
                    resolved_prompt_code,
                    reason,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="当前电话音频桥接不可用。请检查 Gemini Live 配置后重试。",
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            selected_voice_override = _normalize_voice_name_token(voice_name or pending_voice_name)
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
            xml = _build_twilio_media_stream_twiml(
                request=request,
                prompt_code=runtime.template_code,
                from_number=From,
                to_number=To,
                voice_name=resolved_live_voice,
                route_name=route_value,
            )
        else:
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
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")
            turn_url = str(request.url_for("twilio_voice_agent_turn"))
            action_url = twilio_voice_agent_service.build_turn_action_url(turn_url, runtime.template_code)
            call_sid = (CallSid or "").strip()
            if call_sid:
                await twilio_voice_agent_service.ensure_session(
                    db=db,
                    call_sid=call_sid,
                    prompt_code=runtime.template_code,
                )
            xml = twilio_voice_agent_service.build_gather_twiml(
                say_text=opening_text,
                action_url=action_url,
                language=settings.twilio_agent_language,
            )
    else:
        xml = service.build_incoming_to_client_twiml(identity, prompt_code=resolved_prompt_code)

    logger.info(
        (
            "Twilio inbound webhook called. "
            "CallSid=%s From=%s To=%s mode=%s route=%s engine=%s identity=%s prompt_code=%s"
        ),
        CallSid,
        From,
        To,
        mode_value,
        route_value,
        effective_engine,
        identity,
        resolved_prompt_code,
    )
    if pending_override and not any(
        [
            (prompt_code or "").strip(),
            (voice_route or "").strip(),
            (voice_engine or "").strip(),
            (voice_name or "").strip(),
        ]
    ):
        logger.info(
            (
                "Applied pending inbound override for inbound call. "
                "CallSid=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
            ),
            CallSid,
            _normalize_e164_number(To),
            pending_prompt,
            pending_route,
            pending_engine,
            pending_voice_name,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/agent/turn", name="twilio_voice_agent_turn")
async def twilio_voice_agent_turn(
    request: Request,
    db: AsyncSession = Depends(get_db),
    prompt_code: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    SpeechResult: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    call_sid = (CallSid or "").strip() or "unknown-call"
    service = TwilioWebCallService()
    resolved_prompt_code = service.resolve_incoming_prompt_code(prompt_code=prompt_code, to_number=To)
    turn_url = str(request.url_for("twilio_voice_agent_turn"))
    action_url = twilio_voice_agent_service.build_turn_action_url(turn_url, resolved_prompt_code)
    user_text = (SpeechResult or "").strip()

    if not user_text:
        xml = twilio_voice_agent_service.build_gather_twiml(
            say_text=twilio_voice_agent_service.retry_text(),
            action_url=action_url,
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    if twilio_voice_agent_service.is_end_intent(user_text):
        await twilio_voice_agent_service.clear_session(call_sid)
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text=twilio_voice_agent_service.closing_text(),
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    try:
        reply = await twilio_voice_agent_service.generate_reply(
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
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")
    xml = twilio_voice_agent_service.build_gather_twiml(
        say_text=reply,
        action_url=action_url,
        language=settings.twilio_agent_language,
    )
    return Response(content=xml, media_type="application/xml")
