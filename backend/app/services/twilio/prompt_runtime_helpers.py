import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.model_defaults import require_live_model, resolve_vertex_live_model
from app.exceptions import BusinessException
from app.services.chat_service import ChatService
from app.services.prompt_runtime_resolver import PromptRuntimeConfig, resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.test_session_service import TestSessionService

_TWILIO_CLOSING_REQUIRED_ALL = ("ご利用ありがとうございます",)
_TWILIO_CLOSING_REQUIRED_ANY = ("承りました", "承知いたしました", "承知しました")


def _resolve_gemini_live_model(candidate_model: str | None) -> str:
    resolved = require_live_model(
        candidate_model or settings.default_live_model,
        source="Prompt llm_model",
    )
    if settings.google_vertex_enabled:
        return resolve_vertex_live_model(
            resolved,
            fallback_model=settings.default_live_model,
        )
    return resolved


def _build_test_session_service(db: AsyncSession) -> TestSessionService:
    chat_service = ChatService(db)
    return TestSessionService(
        db,
        call_repo=chat_service.call_repo,
        appointment_repo=chat_service.appointment_repo,
        prompt_service=chat_service.prompt_service,
        extract_appointment=chat_service.extract_appointment,
    )


def _extract_opening_sentence(system_instruction: str | None) -> str | None:
    text = (system_instruction or "").strip()
    if text:
        patterns = [
            r"最初のアシスタント発話.*?「([^」]{8,200})」",
            r"会話開始.*?「([^」]{8,200})」",
            r"必ず次の一文.*?「([^」]{8,200})」",
        ]
        for pattern in patterns:
            matched = re.search(pattern, text, flags=re.S)
            if matched:
                first_sentence = matched.group(1).strip()
                if first_sentence:
                    return first_sentence
    return None


def _require_opening_sentence(*, system_instruction: str | None, template_code: str) -> str:
    opening_text = _extract_opening_sentence(system_instruction)
    if opening_text:
        return opening_text
    raise BusinessException(
        f"Twilio prompt template '{template_code}' must define the first assistant utterance in system prompt."
    )


def _build_twilio_session_instruction(
    system_instruction: str | None,
    *,
    opening_text: str | None,
) -> str | None:
    base_instruction = (system_instruction or "").strip()
    played_opening = (opening_text or "").strip()
    if not played_opening:
        return base_instruction or None
    suffix = (
        "\n\n重要: 通話接続直後の冒頭挨拶はTwilio側で再生済みです。"
        f"再生済みの挨拶: 「{played_opening}」"
        "最初のユーザー発話以降は、この挨拶を繰り返さず、直ちに用件ヒアリングを継続してください。"
        "発話本文以外の説明・段取り・思考過程・英語見出しは出力しないでください。"
    )
    if not base_instruction:
        return suffix.strip()
    return f"{base_instruction}{suffix}"


def _is_auto_closing_reply(text: str | None) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if candidate.endswith(("?", "？")):
        return False
    return all(token in candidate for token in _TWILIO_CLOSING_REQUIRED_ALL) and any(
        token in candidate for token in _TWILIO_CLOSING_REQUIRED_ANY
    )


async def _resolve_prompt_runtime(
    *,
    db: AsyncSession,
    prompt_code: str | None,
    model_capability: str = "any",
) -> PromptRuntimeConfig:
    effective_code = (settings.twilio_default_prompt_code or "").strip()
    prompt_service = PromptService(db)
    requested_code = (prompt_code or "").strip() or effective_code
    if not requested_code:
        raise BusinessException("TWILIO_DEFAULT_PROMPT_CODE is not configured.")

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code=requested_code,
        default_code=requested_code,
        fallback_code=None,
        render_system_instruction=True,
        fallback_instruction=None,
        missing_notice=f"Prompt template '{requested_code}' not found or inactive.",
        model_capability=model_capability,
    )
    if runtime.template is None:
        raise BusinessException(f"Prompt template '{requested_code}' not found or inactive.")
    if not (runtime.system_instruction or "").strip():
        raise BusinessException(
            f"Prompt template '{runtime.template_code}' has empty system prompt."
        )
    return runtime


__all__ = (
    "_build_test_session_service",
    "_build_twilio_session_instruction",
    "_extract_opening_sentence",
    "_is_auto_closing_reply",
    "_require_opening_sentence",
    "_resolve_gemini_live_model",
    "_resolve_prompt_runtime",
)
