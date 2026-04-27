"""
Chat service for LLM orchestrations and extracting data.
"""
import json
import random
import re
from datetime import date, datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID

import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.model_defaults import require_generate_model, resolve_generate_model
from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse,
    TestSessionOperationTurnResponse,
    TestSessionFinalizeResponse,
    TestSessionStartResponse,
)
from app.services.chat_runtime_service import ChatRuntimeService
from app.services.extraction_service import ExtractionService
from app.services.llm.exceptions import LLMRateLimitError
from app.services.llm.factory import LLMFactory
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.test_session_service import TestSessionService
from app.services.transcript_sanitizer import find_injected_user_turn_start, sanitize_assistant_turn
from app.utils.datetime_utils import now_tokyo_naive, to_tokyo_naive


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ChatService:
    """Service for handling chat orchestration and appointment extraction."""
    _OP_FLOW_KEY = "appointment_operation_flow"

    _ASSISTANT_PREFIX_PATTERN = re.compile(
        r"^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
        flags=re.IGNORECASE,
    )
    _ASSISTANT_INLINE_PREFIX_PATTERN = re.compile(
        r"(?im)(?:^|\n)\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
    )
    _INJECTED_USER_TURN_PATTERN = re.compile(
        r"(?im)(?:^|\n)\s*(?:user|customer|human|用户|お客様)\s*[:：]",
    )
    _AMOUNT_PATTERN = re.compile(
        r"([0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:kg|ｋｇ|キロ(?:グラム)?|g|ｇ|グラム|トン|ton(?:s)?|t(?![0-9０-９])|吨|噸|m[3３]|m³|㎥|立方メートル|立方米|立方|立米|袋|点|個|台|脚|本|箱|枚))",
        flags=re.IGNORECASE,
    )
    _JP_OPENING_GREETING = (
        "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
    )

    def __init__(self, db: AsyncSession):
        self.db = db
        self.call_repo = CallRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.prompt_service = PromptService(db)

    @staticmethod
    def _generate_simulated_phone() -> str:
        """Generate a JP-style simulated phone number in E.164 format."""
        prefix = random.choice(["70", "80", "90"])
        subscriber = "".join(str(random.randint(0, 9)) for _ in range(8))
        return f"+81{prefix}{subscriber}"

    @classmethod
    def _parse_appointment_time(cls, value: Optional[str]) -> datetime:
        if not value:
            return now_tokyo_naive()

        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return to_tokyo_naive(parsed) or now_tokyo_naive()

    @staticmethod
    def _compute_duration_seconds(started_at: Optional[datetime], ended_at: Optional[datetime]) -> int:
        if not started_at or not ended_at:
            return 0
        return max(0, int((ended_at - started_at).total_seconds()))

    @staticmethod
    def _extract_retry_delay_seconds(error_message: str) -> Optional[int]:
        match = re.search(r"retry in\s+([0-9.]+)s", error_message, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return max(1, int(float(match.group(1))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _looks_like_quota_error(error_message: str) -> bool:
        lowered = error_message.lower()
        keywords = ["429", "quota", "resource_exhausted", "rate limit", "too many requests"]
        return any(keyword in lowered for keyword in keywords)

    @classmethod
    def _build_quota_notice_reply(cls, error_message: str, *, api_key_missing: bool = False) -> str:
        if api_key_missing:
            return (
                "⚠️ 当前未配置 Gemini API Key，暂时无法调用真实模型。"
                "请在后端 .env 中配置可用 Key 后重试。"
            )

        retry_seconds = cls._extract_retry_delay_seconds(error_message)
        retry_text = f"建议约 {retry_seconds} 秒后重试。" if retry_seconds else "请稍后重试。"
        return (
            "⚠️ 当前 Gemini 配额不足（429 RESOURCE_EXHAUSTED），暂时无法调用真实模型。"
            f"{retry_text} 请检查 Google AI Studio 项目的配额与计费设置。"
        )

    @classmethod
    def _sanitize_assistant_response(cls, text: str) -> str:
        return sanitize_assistant_turn(text)

    @classmethod
    def _extract_leading_sentence(cls, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return ""

        first_line = normalized.splitlines()[0].strip() or normalized
        sentence_match = re.match(r"^(.+?[。！？!?])", first_line)
        if sentence_match:
            return sentence_match.group(1).strip()
        return first_line[:80].strip()

    @classmethod
    def _strip_redundant_opening_greeting(
        cls,
        text: str,
        *,
        prior_assistant_messages: list[str],
    ) -> str:
        if not text:
            return ""
        normalized = text.strip()
        if not prior_assistant_messages:
            return normalized

        candidates: list[str] = [cls._JP_OPENING_GREETING]
        for prior in prior_assistant_messages:
            prior_clean = cls._sanitize_assistant_response(prior)
            if not prior_clean:
                continue
            first_line = prior_clean.splitlines()[0].strip()
            if first_line:
                candidates.append(first_line)
            leading_sentence = cls._extract_leading_sentence(prior_clean)
            if leading_sentence:
                candidates.append(leading_sentence)
            break

        unique_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in sorted(candidates, key=len, reverse=True):
            token = candidate.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            unique_candidates.append(token)

        for candidate in unique_candidates:
            if not normalized.startswith(candidate):
                continue
            trimmed = normalized[len(candidate):].lstrip()
            trimmed = re.sub(r"^[\s、，。:：\-]+", "", trimmed).lstrip()
            return trimmed or normalized

        return normalized

    @classmethod
    def _find_injected_user_turn_start(cls, text: str) -> Optional[int]:
        return find_injected_user_turn_start(text)

    @classmethod
    def _normalize_messages(cls, raw_messages: Any) -> list[dict[str, str]]:
        """Normalize stored messages into a safe role/content list."""
        if not isinstance(raw_messages, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role_raw = str(item.get("role", "")).strip().lower()
            role = {
                "human": "user",
                "customer": "user",
                "ai": "assistant",
                "bot": "assistant",
                "model": "assistant",
                "助手": "assistant",
                "アシスタント": "assistant",
            }.get(role_raw, role_raw)
            if role not in {"user", "assistant", "system"}:
                continue
            content = str(item.get("content", "")).strip()
            if role == "assistant":
                content = cls._sanitize_assistant_response(content).strip()
            if not role or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    @classmethod
    def _parse_messages_from_transcript(cls, transcript: Optional[str]) -> list[dict[str, str]]:
        """Fallback: parse transcript text into message list."""
        if not transcript:
            return []

        pattern = re.compile(r"(用户|助手):\s*(.*?)(?=\n(?:用户|助手):\s*|\Z)", flags=re.S)
        parsed: list[dict[str, str]] = []
        for speaker, content in pattern.findall(transcript):
            cleaned = content.strip()
            if speaker == "助手":
                cleaned = cls._sanitize_assistant_response(cleaned).strip()
            if not cleaned:
                continue
            parsed.append(
                {
                    "role": "user" if speaker == "用户" else "assistant",
                    "content": cleaned,
                }
            )
        return parsed

    @staticmethod
    def _resolve_chat_response_mode(call: Call, template: Any) -> tuple[str, Optional[dict[str, Any]]]:
        """
        Decide runtime response format for chat.

        Unified test tab expects conversational text, so force text mode there
        even if prompt template has json_object configured for extraction workflows.
        """
        response_format = getattr(template, "response_format", None) or "text"
        output_schema = getattr(template, "output_schema", None)

        source = (call.extra_data or {}).get("source")
        if source == "test_lab" and response_format == "json_object":
            return "text", None

        return response_format, output_schema

    @staticmethod
    def _first_non_empty(*values: Any) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @classmethod
    def _extract_amount_from_text(cls, text: Optional[str]) -> Optional[str]:
        normalized = cls._first_non_empty(text)
        if not normalized:
            return None
        match = cls._AMOUNT_PATTERN.search(normalized)
        if not match:
            return None
        return match.group(1).strip()

    @classmethod
    def _resolve_amount(cls, raw_data: dict[str, Any], *fallback_texts: Optional[str]) -> Optional[str]:
        numeric_pattern = r"[0-9０-９]+(?:[.,．][0-9０-９]+)?"

        def format_with_unit(value: Optional[str], unit: str) -> Optional[str]:
            if not value:
                return None
            if re.fullmatch(numeric_pattern, value):
                return f"{value} {unit}"
            return value

        direct_amount = cls._first_non_empty(
            raw_data.get("amount"),
            raw_data.get("quantity"),
            raw_data.get("volume"),
            raw_data.get("weight"),
        )
        if direct_amount:
            return direct_amount

        weight_kg = raw_data.get("estimated_weight_kg")
        if isinstance(weight_kg, (int, float)):
            value = int(weight_kg) if float(weight_kg).is_integer() else weight_kg
            return f"{value} kg"

        weight_text = cls._first_non_empty(raw_data.get("weight_kg"), raw_data.get("estimated_weight_kg"))
        if weight_text:
            return format_with_unit(weight_text, "kg")

        volume = raw_data.get("estimated_volume_m3")
        if isinstance(volume, (int, float)):
            value = int(volume) if float(volume).is_integer() else volume
            return f"{value} m3"

        volume_text = cls._first_non_empty(volume)
        if volume_text:
            return format_with_unit(volume_text, "m3")

        for candidate_text in (
            raw_data.get("summary"),
            raw_data.get("appointment_content"),
            raw_data.get("special_notes"),
            *fallback_texts,
        ):
            extracted = cls._extract_amount_from_text(cls._first_non_empty(candidate_text))
            if extracted:
                return extracted

        return None

    @classmethod
    def _resolve_address(cls, raw_data: dict[str, Any]) -> Optional[str]:
        return cls._first_non_empty(
            raw_data.get("pickup_address"),
            raw_data.get("address"),
            raw_data.get("location"),
        )

    @classmethod
    def _resolve_extra_request(cls, raw_data: dict[str, Any]) -> Optional[str]:
        special_notes = cls._first_non_empty(raw_data.get("special_notes"), raw_data.get("extra_request"))
        time_window = cls._first_non_empty(raw_data.get("preferred_time_window"))
        floor = cls._first_non_empty(raw_data.get("floor"))
        elevator = raw_data.get("elevator")

        fragments: list[str] = []
        if special_notes:
            fragments.append(f"備考: {special_notes}")
        if time_window:
            fragments.append(f"希望時間帯: {time_window}")
        if floor:
            fragments.append(f"階数: {floor}")
        if elevator is True:
            fragments.append("エレベーター: あり")
        elif elevator is False:
            fragments.append("エレベーター: なし")

        return " / ".join(fragments) if fragments else None

    @classmethod
    def _resolve_category(cls, extraction_category: Optional[str], raw_data: dict[str, Any]) -> Optional[str]:
        direct = cls._first_non_empty(extraction_category, raw_data.get("category"))
        if direct:
            return direct

        waste_type = raw_data.get("waste_type")
        if isinstance(waste_type, list):
            items = [str(item).strip() for item in waste_type if str(item).strip()]
            if items:
                return "、".join(items)

        items = raw_data.get("items")
        if isinstance(items, list):
            item_names = [str(item).strip() for item in items if str(item).strip()]
            if item_names:
                return "、".join(item_names)

        return None

    @staticmethod
    def _normalize_datetime_text(text: str) -> str:
        return re.sub(r"[\s　]+", "", text or "")

    @classmethod
    def _parse_optional_appointment_time(cls, value: Any) -> Optional[datetime]:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None

        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            return to_tokyo_naive(parsed) or parsed
        except ValueError:
            return cls._extract_datetime_from_text(raw_value)

    @staticmethod
    def _extract_operation_type_from_raw_data(raw_data: dict[str, Any]) -> Optional[str]:
        request_type = str(raw_data.get("request_type") or "").strip().lower()
        if request_type in {"cancel", "update"}:
            return request_type
        return None

    @staticmethod
    def _is_cancelled_appointment(appointment: Appointment) -> bool:
        extra_data = appointment.extra_data if isinstance(appointment.extra_data, dict) else {}
        lifecycle_status = str(extra_data.get("lifecycle_status") or "").strip().lower()
        return lifecycle_status == "cancelled"

    @classmethod
    def _build_update_changes_from_extraction(cls, raw_data: dict[str, Any]) -> dict[str, str]:
        change_set = raw_data.get("change_set")
        source = change_set if isinstance(change_set, dict) else raw_data
        changes: dict[str, str] = {}

        appointment_time = cls._first_non_empty(source.get("appointment_time"))
        if appointment_time:
            changes["appointment"] = appointment_time

        pickup_address = cls._first_non_empty(source.get("pickup_address"))
        if pickup_address:
            changes["address"] = pickup_address

        amount = cls._first_non_empty(source.get("amount"))
        if not amount and source.get("estimated_volume_m3") is not None:
            amount = f"{source.get('estimated_volume_m3')}m3"
        if amount:
            changes["amount"] = amount

        category = cls._resolve_category(cls._first_non_empty(source.get("category")), source)
        if category:
            changes["category"] = category

        return changes

    @classmethod
    def _score_extracted_operation_candidate(
        cls,
        appointment: Appointment,
        related_call: Optional[Call],
        *,
        raw_data: dict[str, Any],
        target_time: Optional[datetime],
    ) -> int:
        score = 0

        if target_time and isinstance(appointment.appointment, datetime):
            if appointment.appointment.date() != target_time.date():
                return 0
            score += 2
            if (
                appointment.appointment.hour == target_time.hour
                and appointment.appointment.minute == target_time.minute
            ):
                score += 2

        caller_name = cls._first_non_empty(raw_data.get("caller_name"))
        if caller_name and (
            cls._loosely_matches(caller_name, appointment.caller_name)
            or cls._loosely_matches(caller_name, getattr(related_call, "caller_name", None))
        ):
            score += 2

        company = cls._first_non_empty(raw_data.get("company"))
        if company and cls._loosely_matches(company, appointment.company):
            score += 1

        pickup_address = cls._first_non_empty(raw_data.get("pickup_address"))
        if pickup_address and cls._loosely_matches(pickup_address, appointment.address):
            score += 1

        contact_phone = cls._normalize_phone_number(cls._first_non_empty(raw_data.get("contact_phone")))
        candidate_phone = cls._normalize_phone_number(getattr(related_call, "counterpart", None))
        if contact_phone and candidate_phone:
            shorter, longer = sorted([contact_phone, candidate_phone], key=len)
            if contact_phone == candidate_phone or (len(shorter) >= 8 and longer.endswith(shorter)):
                score += 1

        return score

    async def _resolve_extracted_operation_target(
        self,
        *,
        call: Call,
        raw_data: dict[str, Any],
    ) -> Optional[Appointment]:
        target_id_raw = str(raw_data.get("target_appointment_id") or "").strip()
        if target_id_raw:
            try:
                target = await self.appointment_repo.get(UUID(target_id_raw))
            except (TypeError, ValueError):
                target = None
            if target and not self._is_cancelled_appointment(target):
                return target

        target_time = self._parse_optional_appointment_time(
            raw_data.get("original_appointment_time") or raw_data.get("appointment_time")
        )
        caller_name = self._first_non_empty(raw_data.get("caller_name"))
        company = self._first_non_empty(raw_data.get("company"))
        contact_phone = self._first_non_empty(raw_data.get("contact_phone"))
        query_counterpart = contact_phone if contact_phone and contact_phone.startswith("+") else None

        candidate_rows = await self.appointment_repo.search_operation_candidates_with_call(
            caller_name=caller_name,
            company=company,
            counterpart=query_counterpart,
            appointment_date=target_time.date() if target_time else None,
            limit=50,
        )

        scored_candidates: list[tuple[int, datetime, Appointment]] = []
        for appointment, related_call in candidate_rows:
            if appointment.call_id == call.id or self._is_cancelled_appointment(appointment):
                continue
            score = self._score_extracted_operation_candidate(
                appointment,
                related_call,
                raw_data=raw_data,
                target_time=target_time,
            )
            threshold = 4 if target_time else 3
            if score >= threshold:
                scored_candidates.append((score, appointment.timestamp or datetime.min, appointment))

        scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored_candidates[0][2] if scored_candidates else None

    async def _try_apply_extracted_operation_request(
        self,
        *,
        call: Call,
        raw_data: dict[str, Any],
        extraction_summary: str,
        extraction_confidence: float,
        extra_data: dict[str, Any],
    ) -> Optional[ExtractionResponse]:
        operation = self._extract_operation_type_from_raw_data(raw_data)
        if operation not in {"cancel", "update"}:
            return None

        target = await self._resolve_extracted_operation_target(call=call, raw_data=raw_data)
        if not target:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={
                    "operation": operation,
                    "resolution_status": "target_not_found",
                    "extracted_data": raw_data,
                },
                confidence=extraction_confidence,
                message="检测到预约变更/取消请求，但未能匹配目标预约，已跳过新预约创建",
            )

        pending_changes = self._build_update_changes_from_extraction(raw_data) if operation == "update" else {}
        if operation == "update" and not pending_changes:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={
                    "operation": operation,
                    "target_appointment_id": str(target.id),
                    "resolution_status": "missing_update_changes",
                    "extracted_data": raw_data,
                },
                confidence=extraction_confidence,
                message="检测到预约变更请求并找到目标预约，但未抽取到变更内容，已跳过新预约创建",
            )

        await self._execute_operation_flow_action(
            call=call,
            appointment=target,
            operation=operation,
            pending_changes=pending_changes,
            flow={"operation": operation, "pending_note": extraction_summary},
            extra_data=dict(extra_data),
            user_message=extraction_summary,
        )
        await self.db.commit()

        operation_execution = dict(call.extra_data or {}).get("operation_execution")
        operation_event_id: Optional[UUID] = None
        if isinstance(operation_execution, dict):
            try:
                operation_event_id = UUID(str(operation_execution.get("appointment_id")))
            except (TypeError, ValueError):
                operation_event_id = None

        return ExtractionResponse(
            success=True,
            appointment_id=operation_event_id,
            extracted_data={
                "operation": operation,
                "target_appointment_id": str(target.id),
                "operation_event_id": str(operation_event_id) if operation_event_id else None,
                "changes": pending_changes,
                "resolution_status": "executed_from_llm_extraction",
                "extracted_data": raw_data,
            },
            confidence=extraction_confidence,
            message="检测到预约变更/取消请求，已更新目标预约并创建操作事件",
        )

    @staticmethod
    def _detect_operation_intent(text: str) -> Optional[str]:
        normalized = text.strip().lower()
        if not normalized:
            return None

        cancel_keywords = [
            "キャンセル",
            "取消",
            "取り消",
            "中止",
            "cancel",
        ]
        update_keywords = [
            "変更",
            "修正",
            "更新",
            "変え",
            "改め",
            "reschedule",
            "update",
        ]

        if any(keyword in normalized for keyword in cancel_keywords):
            return "cancel"
        if any(keyword in normalized for keyword in update_keywords):
            return "update"
        return None

    @staticmethod
    def _normalize_identity_token(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = value.strip().lower()
        return re.sub(r"[\s_\-]+", "", normalized)

    @classmethod
    def _is_generic_caller_name(cls, value: Optional[str]) -> bool:
        normalized = cls._normalize_identity_token(value)
        generic_tokens = {
            "",
            "testcaller",
            "testuser",
            "chatuser",
            "caller",
            "unknown",
            "guest",
            "visitor",
            "anonymous",
            "anon",
            "お客様",
            "顧客",
            "利用者",
            "テスト",
            "テストユーザー",
            "テスト利用者",
        }
        return normalized in generic_tokens

    @classmethod
    def _is_placeholder_counterpart(cls, value: Optional[str]) -> bool:
        normalized = cls._normalize_identity_token(value)
        placeholder_tokens = {
            "",
            "chatuser",
            "testuser",
            "unknown",
            "anonymous",
            "guest",
            "visitor",
            "none",
            "null",
            "-",
        }
        return normalized in placeholder_tokens

    @staticmethod
    def _is_affirmative(text: str) -> bool:
        normalized = text.strip().lower()
        positives = [
            "はい",
            "ええ",
            "yes",
            "ok",
            "okay",
            "是",
            "好的",
            "没问题",
            "それで大丈夫",
            "お願いします",
        ]
        return any(token in normalized for token in positives)

    @staticmethod
    def _is_negative(text: str) -> bool:
        normalized = text.strip().lower()
        negatives = [
            "いいえ",
            "違います",
            "違う",
            "no",
            "不是",
            "不对",
            "やめ",
        ]
        return any(token in normalized for token in negatives)

    @staticmethod
    def _extract_target_date(text: str) -> Optional[date]:
        if not text:
            return None

        normalized_text = ChatService._normalize_datetime_text(text)
        patterns = [
            r"(\d{4})(?:[/-]|年(?:の)?)(\d{1,2})(?:[/-]|月(?:の)?)(\d{1,2})(?:日)?",
            r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized_text)
            if not match:
                continue
            try:
                year, month, day = (int(part) for part in match.groups())
                return date(year, month, day)
            except ValueError:
                continue
        return None

    @classmethod
    def _extract_datetime_parts_from_text(cls, text: str) -> tuple[Optional[datetime], bool]:
        if not text:
            return None, False

        normalized_text = cls._normalize_datetime_text(text)
        match = re.search(
            r"(\d{4})(?:[/-]|年(?:の)?)(\d{1,2})(?:[/-]|月(?:の)?)(\d{1,2})(?:日)?(?:[^\d]{0,8}(\d{1,2})(?::|時)(\d{1,2})?(?:分)?)?",
            normalized_text,
        )
        if not match:
            return None, False

        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        has_time = bool(match.group(4))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        try:
            return datetime(year, month, day, hour, minute), has_time
        except ValueError:
            return None, False

    @classmethod
    def _extract_datetime_from_text(cls, text: str) -> Optional[datetime]:
        parsed, _ = cls._extract_datetime_parts_from_text(text)
        return parsed

    @staticmethod
    def _extract_address_from_text(text: str) -> Optional[str]:
        if not text:
            return None

        patterns = [
            r"(?:住所|地址|回収先|pickup\s*address)\s*(?:は|为|:|：)?\s*(.+)",
            r"(東京都|北海道|(?:京都|大阪)府|.{2,3}県.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip("。 　")
            if candidate:
                return candidate
        return None

    @classmethod
    def _extract_update_changes(cls, text: str) -> dict[str, str]:
        changes: dict[str, str] = {}

        appointment_dt = cls._extract_datetime_from_text(text)
        if appointment_dt:
            changes["appointment"] = appointment_dt.isoformat()

        amount = cls._extract_amount_from_text(text)
        if amount:
            changes["amount"] = amount

        address = cls._extract_address_from_text(text)
        if address:
            changes["address"] = address

        category_match = re.search(r"(?:品目|種類|类别|category)\s*(?:は|为|:|：)?\s*([^\n。]+)", text, flags=re.IGNORECASE)
        if category_match:
            category = category_match.group(1).strip()
            if category:
                changes["category"] = category

        return changes

    @staticmethod
    def _format_appointment_brief(appointment: Appointment, index: Optional[int] = None) -> str:
        prefix = f"[{index}] " if index is not None else ""
        appointment_time = (
            appointment.appointment.strftime("%Y-%m-%d %H:%M")
            if isinstance(appointment.appointment, datetime)
            else str(appointment.appointment)
        )
        company = appointment.company or "-"
        amount = appointment.amount or "-"
        address = appointment.address or "-"
        return (
            f"{prefix}予約日時: {appointment_time} / "
            f"氏名: {appointment.caller_name} / 会社: {company} / 数量: {amount} / 住所: {address}"
        )

    @staticmethod
    def _select_candidate_id_from_text(text: str, candidate_ids: list[str]) -> Optional[str]:
        normalized = text.strip()
        if not normalized or not candidate_ids:
            return None

        for candidate_id in candidate_ids:
            if candidate_id in normalized:
                return candidate_id

        number_match = re.search(r"\b([1-9]\d*)\b", normalized)
        if number_match:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(candidate_ids):
                return candidate_ids[index]
        return None

    @classmethod
    def _build_operation_conversation_snapshot(
        cls,
        call: Call,
        *,
        user_message: str,
        assistant_message: str,
    ) -> list[dict[str, str]]:
        messages = cls._normalize_messages((call.extra_data or {}).get("messages"))
        user_text = user_message.strip()
        assistant_text = cls._sanitize_assistant_response(assistant_message)

        if user_text:
            messages.append({"role": "user", "content": user_text})
        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})
        return messages

    @staticmethod
    def _build_operation_event_summary(
        *,
        operation: str,
        target: Appointment,
        pending_changes: dict[str, str],
        target_brief: str,
    ) -> str:
        if operation == "cancel":
            return f"既存予約をキャンセル。対象: {target_brief}"

        changed_parts: list[str] = []
        if "appointment" in pending_changes:
            changed_parts.append("日時")
        if "address" in pending_changes:
            changed_parts.append("住所")
        if "amount" in pending_changes:
            changed_parts.append("数量")
        if "category" in pending_changes:
            changed_parts.append("カテゴリ")

        changed_text = "・".join(changed_parts) if changed_parts else "項目不明"
        caller_name = target.caller_name or "不明"
        return f"{caller_name}様の既存予約を変更。変更項目: {changed_text}"

    async def _execute_operation_flow_action(
        self,
        *,
        call: Call,
        appointment: Appointment,
        operation: str,
        pending_changes: dict[str, str],
        flow: dict[str, Any],
        extra_data: dict[str, Any],
        user_message: str,
    ) -> str:
        now_dt = now_tokyo_naive()
        now_iso = now_dt.isoformat()
        appointment_extra_data = dict(appointment.extra_data or {})

        before_snapshot = {
            "appointment": appointment.appointment.isoformat() if isinstance(appointment.appointment, datetime) else None,
            "address": appointment.address,
            "amount": appointment.amount,
            "category": appointment.category,
            "lifecycle_status": appointment_extra_data.get("lifecycle_status", "active"),
        }

        if operation == "cancel":
            appointment_extra_data["lifecycle_status"] = "cancelled"
        else:
            if "appointment" in pending_changes:
                appointment.appointment = self._parse_appointment_time(pending_changes["appointment"])
            if "address" in pending_changes:
                appointment.address = pending_changes["address"]
            if "amount" in pending_changes:
                appointment.amount = pending_changes["amount"]
            if "category" in pending_changes:
                appointment.category = pending_changes["category"]
            appointment_extra_data["lifecycle_status"] = "active"

        appointment_extra_data["last_operation_flow"] = {
            "operation": operation,
            "confirmed_at": now_iso,
            "changes": pending_changes,
            "note": flow.get("pending_note"),
            "call_id": str(call.id),
        }
        appointment_extra_data["latest_operation_type"] = operation
        appointment_extra_data["latest_operation_at"] = now_iso
        appointment_extra_data["latest_operation_call_id"] = str(call.id)
        appointment.extra_data = appointment_extra_data

        result_summary = self._format_appointment_brief(appointment)
        done_label = "キャンセルが完了しました。" if operation == "cancel" else "変更が完了しました。"
        done_message = f"{done_label}\n{result_summary}"

        after_snapshot = {
            "appointment": appointment.appointment.isoformat() if isinstance(appointment.appointment, datetime) else None,
            "address": appointment.address,
            "amount": appointment.amount,
            "category": appointment.category,
            "lifecycle_status": appointment_extra_data.get("lifecycle_status", "active"),
        }
        conversation_snapshot = self._build_operation_conversation_snapshot(
            call,
            user_message=user_message,
            assistant_message=done_message,
        )

        operation_event_data = {
            "call_id": call.id,
            "timestamp": now_dt,
            "caller_name": appointment.caller_name or call.caller_name or "Unknown",
            "company": appointment.company,
            "appointment": appointment.appointment or now_dt,
            "category": appointment.category,
            "amount": appointment.amount,
            "address": appointment.address,
            "summary": self._build_operation_event_summary(
                operation=operation,
                target=appointment,
                pending_changes=pending_changes,
                target_brief=result_summary,
            ),
            "extra_request": appointment.extra_request,
            "operation": operation,
            "prompt_id": appointment.prompt_id,
            "type_name": appointment.type_name,
            "extracted_data": {
                "operation": operation,
                "target_appointment_id": str(appointment.id),
                "changes": pending_changes,
                "before": before_snapshot,
                "after": after_snapshot,
                "confirmed_at": now_iso,
            },
            "extra_data": {
                "simulation": bool(extra_data.get("simulation", False)),
                "source": extra_data.get("source", "chat"),
                "template_code": extra_data.get("template_code"),
                "llm_provider": extra_data.get("llm_provider"),
                "llm_model": extra_data.get("llm_model"),
                "target_appointment_id": str(appointment.id),
                "target_call_id": str(appointment.call_id) if appointment.call_id else None,
                "operation_flow": {
                    "operation": operation,
                    "confirmed_at": now_iso,
                },
            },
            "raw_messages": {
                "extraction_source": "operation_flow",
                "conversation": conversation_snapshot,
                "operation": operation,
                "target_appointment_id": str(appointment.id),
            },
        }

        operation_event = await self.appointment_repo.create(operation_event_data)
        appointment_extra_data["latest_operation_event_id"] = str(operation_event.id)
        appointment.extra_data = appointment_extra_data
        await self.db.commit()

        extra_data["operation_execution"] = {
            "operation": operation,
            "appointment_id": str(operation_event.id),
            "target_appointment_id": str(appointment.id),
            "confirmed_at": now_iso,
        }
        extra_data.pop(self._OP_FLOW_KEY, None)
        call.extra_data = extra_data

        return done_message

    @staticmethod
    def _build_disambiguation_question(field_key: str) -> str:
        prompts = {
            "appointment_time": "回収希望日時（時刻まで）を教えてください。",
            "address": "回収先住所を教えてください。",
            "amount": "回収量（例: 3kg / 2m3）を教えてください。",
            "company": "会社名を教えてください。",
            "caller_name": "ご予約者様のお名前を教えてください。",
        }
        question = prompts.get(field_key, "予約内容を区別するため、追加情報を教えてください。")
        return f"候補が複数あるため、確認します。{question}"

    @classmethod
    def _choose_disambiguation_field(cls, candidates: list[Appointment], hints: dict[str, str]) -> Optional[str]:
        if len(candidates) <= 1:
            return None

        def values_for(key: str) -> set[str]:
            values: set[str] = set()
            for item in candidates:
                raw: Optional[str]
                if key == "appointment_time":
                    raw = (
                        item.appointment.strftime("%Y-%m-%d %H:%M")
                        if isinstance(item.appointment, datetime)
                        else None
                    )
                elif key == "address":
                    raw = item.address
                elif key == "amount":
                    raw = item.amount
                elif key == "company":
                    raw = item.company
                elif key == "caller_name":
                    raw = item.caller_name
                else:
                    raw = None
                normalized = cls._normalize_match_text(raw)
                if normalized:
                    values.add(normalized)
            return values

        candidate_fields = ["appointment_time", "address", "amount", "company", "caller_name"]
        for field in candidate_fields:
            if len(values_for(field)) <= 1:
                continue
            if field == "company" and cls._first_non_empty(hints.get("company")):
                continue
            if field == "caller_name" and cls._first_non_empty(hints.get("caller_name")):
                continue
            return field
        return None

    @classmethod
    def _extract_disambiguation_answer(cls, field_key: str, text: str) -> Optional[str]:
        message = text.strip()
        if not message:
            return None

        if field_key == "appointment_time":
            parsed_dt, has_time = cls._extract_datetime_parts_from_text(message)
            if parsed_dt:
                return parsed_dt.strftime("%Y-%m-%d %H:%M") if has_time else parsed_dt.strftime("%Y-%m-%d")
            return None
        if field_key == "address":
            return cls._extract_address_from_text(message) or message
        if field_key == "amount":
            return cls._extract_amount_from_text(message)
        if field_key == "company":
            company, _ = cls._extract_company_name_pair(message)
            return company or cls._extract_company_hint(message) or message
        if field_key == "caller_name":
            _, caller_name = cls._extract_company_name_pair(message)
            return caller_name or cls._extract_name_hint(message) or message
        return message

    @classmethod
    def _candidate_matches_disambiguation(
        cls,
        candidate: Appointment,
        field_key: str,
        answer: str,
    ) -> bool:
        answer_text = cls._normalize_match_text(answer)
        if not answer_text:
            return False

        if field_key == "appointment_time":
            if not isinstance(candidate.appointment, datetime):
                return False
            parsed_dt, has_time = cls._extract_datetime_parts_from_text(answer)
            if not parsed_dt:
                return False
            if has_time:
                return (
                    candidate.appointment.year == parsed_dt.year
                    and candidate.appointment.month == parsed_dt.month
                    and candidate.appointment.day == parsed_dt.day
                    and candidate.appointment.hour == parsed_dt.hour
                    and candidate.appointment.minute == parsed_dt.minute
                )
            return candidate.appointment.date() == parsed_dt.date()

        source_map = {
            "address": candidate.address,
            "amount": candidate.amount,
            "company": candidate.company,
            "caller_name": candidate.caller_name,
        }
        candidate_value = source_map.get(field_key)
        return cls._loosely_matches(answer, candidate_value)

    @staticmethod
    def _normalize_phone_number(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"\D+", "", value)

    @staticmethod
    def _normalize_match_text(value: Optional[str]) -> str:
        if not value:
            return ""
        lowered = value.strip().lower()
        return re.sub(r"[\s　]+", "", lowered)

    @classmethod
    def _loosely_matches(cls, left: Optional[str], right: Optional[str]) -> bool:
        left_norm = cls._normalize_match_text(left)
        right_norm = cls._normalize_match_text(right)
        if not left_norm or not right_norm:
            return False
        return left_norm in right_norm or right_norm in left_norm

    @classmethod
    def _extract_company_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        patterns = [
            r"(?:会社名|会社|company|公司)\s*(?:は|:|：)?\s*([^\n。]{1,80})",
            r"([^\s、。]{1,80}会社)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip(" 　。")
            candidate = re.split(
                r"(?:予約日|回収希望日|電話番号|連絡先|氏名|名前|担当者|,|，|、)",
                candidate,
                maxsplit=1,
            )[0].strip(" 　。")
            if candidate:
                return candidate
        return None

    @classmethod
    def _extract_company_hint_from_expected_reply(cls, text: str) -> Optional[str]:
        if not text:
            return None

        normalized = text.strip()
        if not normalized:
            return None

        if re.fullmatch(r"個人(?:です|でお願いします|でございます)?[。]?", normalized):
            return "個人"

        cleaned = re.sub(r"(?:です|でございます|でお願いします)$", "", normalized).strip(" 　。")
        if not cleaned:
            return None

        invalid_tokens = {
            "はい",
            "いいえ",
            "お願いします",
            "変更",
            "キャンセル",
            "予約",
            "回収",
            "住所",
            "日時",
            "電話番号",
            "連絡先",
        }
        if cleaned in invalid_tokens:
            return None
        if re.search(r"[?？]", cleaned):
            return None

        return cleaned

    @classmethod
    def _extract_name_hint_from_expected_reply(cls, text: str) -> Optional[str]:
        if not text:
            return None

        normalized = text.strip()
        if not normalized:
            return None

        cleaned = re.sub(r"(?:です|と申します|でございます)$", "", normalized).strip(" 　。")
        if not cleaned:
            return None

        if (
            cls._is_generic_caller_name(cleaned)
            or "会社" in cleaned
            or "会社の" in cleaned
            or re.search(r"[?？]", cleaned)
        ):
            return None
        return cleaned

    @classmethod
    def _extract_company_name_pair(cls, text: str) -> tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None

        match = re.search(
            r"([^\s、。]{1,80}会社)\s*の\s*([^\s、。]{1,40})(?:です|と申します|でございます)?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, None

        company = match.group(1).strip(" 　。")
        caller_name = match.group(2).strip(" 　。")
        caller_name = re.sub(r"(?:です|と申します|でございます)$", "", caller_name).strip(" 　。")
        if cls._is_generic_caller_name(caller_name):
            caller_name = None
        return company or None, caller_name or None

    @classmethod
    def _extract_name_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        compact_text = re.sub(r"[\s　]+", "", text)
        patterns = [
            r"(?:お名前|名前|氏名|担当者(?:名)?|依頼者)\s*(?:は|:|：)?\s*([^\n、。]{1,60})",
            r"([^\s、。]{1,40})と申します",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip(" 　。")
            if (
                candidate
                and not cls._is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
            ):
                return candidate

        trailing_intro = re.search(
            r"(?:^|[、,。])([^、,。]{1,32})(?:です|と申します|でございます)(?:[。.]|$)",
            compact_text,
        )
        if trailing_intro:
            candidate = trailing_intro.group(1).strip(" 　。")
            invalid_fragments = [
                "予約",
                "変更",
                "キャンセル",
                "予定",
                "回収",
                "したい",
                "希望",
                "お願い",
                "はい",
                "いいえ",
            ]
            if (
                candidate
                and not cls._is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
                and not any(fragment in candidate for fragment in invalid_fragments)
            ):
                return candidate

        short_self_intro = re.fullmatch(r"\s*([^\s、。]{1,32})\s*です\s*[。]?\s*", text)
        if short_self_intro:
            candidate = short_self_intro.group(1).strip(" 　。")
            invalid_fragments = [
                "予約",
                "変更",
                "キャンセル",
                "予定",
                "回収",
                "したい",
                "希望",
                "お願い",
                "です",
            ]
            if (
                candidate
                and not cls._is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
                and not any(fragment in candidate for fragment in invalid_fragments)
            ):
                return candidate
        return None

    @classmethod
    def _extract_phone_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
        if not match:
            return None

        candidate = match.group(1).strip()
        normalized = cls._normalize_phone_number(candidate)
        if len(normalized) < 9:
            return None
        return candidate

    @classmethod
    def _collect_operation_identity_hints(
        cls,
        call: Call,
        user_message: str,
        *,
        base_hints: Optional[dict[str, str]] = None,
        expected_identity_key: Optional[str] = None,
    ) -> dict[str, str]:
        hints: dict[str, str] = dict(base_hints or {})

        message_company, message_caller_name = cls._extract_company_name_pair(user_message)

        caller_name = cls._first_non_empty(message_caller_name, cls._extract_name_hint(user_message))
        if not caller_name:
            caller_name = cls._first_non_empty(hints.get("caller_name"))
        if not caller_name:
            call_name = cls._first_non_empty(call.caller_name)
            if call_name and not cls._is_generic_caller_name(call_name):
                caller_name = call_name
        if caller_name and not cls._is_generic_caller_name(caller_name):
            hints["caller_name"] = caller_name
        else:
            hints.pop("caller_name", None)

        company = cls._first_non_empty(message_company, cls._extract_company_hint(user_message))
        if not company and expected_identity_key == "company":
            company = cls._extract_company_hint_from_expected_reply(user_message)
        if not company:
            company = cls._first_non_empty(hints.get("company"))
        if company:
            hints["company"] = company
        else:
            hints.pop("company", None)

        counterpart = cls._extract_phone_hint(user_message)
        if not counterpart:
            counterpart = cls._first_non_empty(hints.get("counterpart"))
        if not counterpart:
            call_counterpart = cls._first_non_empty(call.counterpart)
            if call_counterpart and not cls._is_placeholder_counterpart(call_counterpart):
                counterpart = call_counterpart
        if counterpart and not cls._is_placeholder_counterpart(counterpart):
            hints["counterpart"] = counterpart
        else:
            hints.pop("counterpart", None)

        appointment_date = cls._extract_target_date(user_message)
        if not appointment_date and expected_identity_key == "appointment_date":
            appointment_date = cls._extract_target_date(f"{now_tokyo_naive().year}年{user_message}")
        if appointment_date:
            hints["appointment_date"] = appointment_date.isoformat()
        else:
            existing_date = cls._parse_hint_date(hints)
            if existing_date:
                hints["appointment_date"] = existing_date.isoformat()
            else:
                hints.pop("appointment_date", None)

        if expected_identity_key == "caller_name" and "caller_name" not in hints:
            fallback_name = cls._extract_name_hint_from_expected_reply(user_message)
            if fallback_name:
                hints["caller_name"] = fallback_name

        return hints

    @staticmethod
    def _count_operation_identity_hints(hints: dict[str, str]) -> int:
        keys = ("caller_name", "company", "counterpart", "appointment_date")
        return sum(1 for key in keys if str(hints.get(key) or "").strip())

    @staticmethod
    def _parse_hint_date(hints: dict[str, str]) -> Optional[date]:
        raw_value = str(hints.get("appointment_date") or "").strip()
        if not raw_value:
            return None
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            return None

    @classmethod
    def _score_operation_candidate(
        cls,
        appointment: Appointment,
        related_call: Optional[Call],
        hints: dict[str, str],
    ) -> int:
        matched_keys: set[str] = set()

        hint_name = hints.get("caller_name")
        if hint_name and (
            cls._loosely_matches(hint_name, appointment.caller_name)
            or cls._loosely_matches(hint_name, getattr(related_call, "caller_name", None))
        ):
            matched_keys.add("caller_name")

        hint_company = hints.get("company")
        if hint_company and cls._loosely_matches(hint_company, appointment.company):
            matched_keys.add("company")

        hint_phone = cls._normalize_phone_number(hints.get("counterpart"))
        candidate_phone = cls._normalize_phone_number(getattr(related_call, "counterpart", None))
        if hint_phone and candidate_phone:
            shorter, longer = sorted([hint_phone, candidate_phone], key=len)
            if hint_phone == candidate_phone or (len(shorter) >= 8 and longer.endswith(shorter)):
                matched_keys.add("counterpart")

        hint_date = cls._parse_hint_date(hints)
        if hint_date and isinstance(appointment.appointment, datetime) and appointment.appointment.date() == hint_date:
            matched_keys.add("appointment_date")

        return len(matched_keys)

    @classmethod
    def _next_identity_question_key(cls, hints: dict[str, str], *, no_match: bool = False) -> str:
        collect_order = ("caller_name", "company", "appointment_date", "counterpart")
        verify_order = ("appointment_date", "caller_name", "company", "counterpart")
        order = verify_order if no_match else collect_order
        for key in order:
            if not str(hints.get(key) or "").strip():
                return key
        return order[0]

    @classmethod
    def _build_identity_single_question(cls, key: str) -> str:
        prompts = {
            "caller_name": "ご予約者様のお名前を教えてください。",
            "company": "会社名を教えてください。個人の場合は「個人」で問題ありません。",
            "counterpart": "ご連絡先の電話番号を教えてください。",
            "appointment_date": "回収希望日を教えてください。（例: 2026年4月1日）",
        }
        return prompts.get(key, "確認のため、予約情報をもう一度教えてください。")

    @classmethod
    def _build_operation_identity_prompt(
        cls,
        hints: dict[str, str],
        *,
        no_match: bool = False,
        mismatch_count: int = 0,
    ) -> str:
        next_key = cls._next_identity_question_key(hints, no_match=no_match)
        question = cls._build_identity_single_question(next_key)
        known_count = cls._count_operation_identity_hints(hints)

        if no_match and mismatch_count >= 2:
            return (
                "ありがとうございます。現在の情報では対象予約を特定できませんでした。"
                f" {question}"
            )
        if no_match:
            return f"ありがとうございます。現在の情報では対象予約を特定できませんでした。確認のため、{question}"
        if known_count == 0:
            return f"予約変更・キャンセル対象を確認します。まず、{question}"
        return f"ありがとうございます。続けて、{question}"

    async def _find_operation_candidates(
        self,
        call: Call,
        user_message: str,
        *,
        base_hints: Optional[dict[str, str]] = None,
        expected_identity_key: Optional[str] = None,
    ) -> tuple[list[Appointment], dict[str, str]]:
        hints = self._collect_operation_identity_hints(
            call,
            user_message,
            base_hints=base_hints,
            expected_identity_key=expected_identity_key,
        )
        if self._count_operation_identity_hints(hints) < 3:
            return [], hints

        appointment_date = self._parse_hint_date(hints)
        counterpart = self._first_non_empty(hints.get("counterpart"))
        query_counterpart = counterpart if counterpart and counterpart.startswith("+") else None

        candidate_rows = await self.appointment_repo.search_operation_candidates_with_call(
            caller_name=self._first_non_empty(hints.get("caller_name")),
            company=self._first_non_empty(hints.get("company")),
            counterpart=query_counterpart,
            appointment_date=appointment_date,
            limit=30,
        )

        scored_candidates: list[tuple[int, datetime, Appointment]] = []
        for appointment, related_call in candidate_rows:
            score = self._score_operation_candidate(appointment, related_call, hints)
            if score >= 3:
                timestamp = appointment.timestamp or datetime.min
                scored_candidates.append((score, timestamp, appointment))

        scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored_candidates[:5]], hints

    async def _load_operation_candidates_by_ids(self, candidate_ids: list[str]) -> list[Appointment]:
        candidates: list[Appointment] = []
        for candidate_id in candidate_ids:
            try:
                candidate_uuid = UUID(str(candidate_id))
            except (TypeError, ValueError):
                continue
            candidate = await self.appointment_repo.get(candidate_uuid)
            if candidate:
                candidates.append(candidate)
        candidates.sort(
            key=lambda item: item.timestamp or datetime.min,
            reverse=True,
        )
        return candidates

    async def _handle_appointment_operation_flow(self, call: Call, user_message: str) -> Optional[str]:
        extra_data = dict(call.extra_data or {})
        flow = dict(extra_data.get(self._OP_FLOW_KEY) or {"status": "idle"})
        status = str(flow.get("status", "idle"))

        if status == "idle":
            intent = self._detect_operation_intent(user_message)
            if intent not in {"update", "cancel"}:
                return None

            candidates, identity_hints = await self._find_operation_candidates(call, user_message)
            if not candidates:
                hint_count = self._count_operation_identity_hints(identity_hints)
                mismatch_count = 1 if hint_count >= 3 else 0
                no_match = hint_count >= 3
                expected_identity_key = self._next_identity_question_key(identity_hints, no_match=no_match)
                extra_data[self._OP_FLOW_KEY] = {
                    "status": "await_target_input",
                    "operation": intent,
                    "identity_hints": identity_hints,
                    "mismatch_count": mismatch_count,
                    "expected_identity_key": expected_identity_key,
                }
                call.extra_data = extra_data
                return self._build_operation_identity_prompt(
                    identity_hints,
                    no_match=no_match,
                    mismatch_count=mismatch_count,
                )

            flow = {
                "status": "await_target_confirmation",
                "operation": intent,
                "candidate_ids": [str(item.id) for item in candidates],
            }
            flow.pop("expected_identity_key", None)
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data

            operation_label = "変更" if intent == "update" else "キャンセル"
            if len(candidates) == 1:
                return (
                    f"{operation_label}のご依頼ですね。対象候補は次の予約です。\n"
                    f"{self._format_appointment_brief(candidates[0])}\n"
                    "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
                )

            disambiguation_field = self._choose_disambiguation_field(candidates, identity_hints)
            if disambiguation_field:
                flow["status"] = "await_target_disambiguation"
                flow["disambiguation_field"] = disambiguation_field
                flow["identity_hints"] = identity_hints
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                return self._build_disambiguation_question(disambiguation_field)

            flow["status"] = "await_target_confirmation"
            flow["candidate_ids"] = [str(candidates[0].id)]
            flow["identity_hints"] = identity_hints
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data
            return (
                "同一条件の予約が複数見つかったため、最新の予約を対象候補として確認します。\n"
                f"{self._format_appointment_brief(candidates[0])}\n"
                "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
            )

        if status == "await_target_input":
            selected: Optional[Appointment] = None
            possible_uuid = re.search(
                r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
                user_message,
            )
            if possible_uuid:
                try:
                    selected = await self.appointment_repo.get(UUID(possible_uuid.group(0)))
                except (TypeError, ValueError):
                    selected = None

            base_hints = flow.get("identity_hints")
            if not isinstance(base_hints, dict):
                base_hints = {}
            expected_identity_key_raw = str(flow.get("expected_identity_key") or "").strip()
            expected_identity_key = expected_identity_key_raw or None
            candidates, identity_hints = (
                (
                    [selected],
                    self._collect_operation_identity_hints(
                        call,
                        user_message,
                        base_hints=base_hints,
                        expected_identity_key=expected_identity_key,
                    ),
                )
                if selected
                else await self._find_operation_candidates(
                    call,
                    user_message,
                    base_hints=base_hints,
                    expected_identity_key=expected_identity_key,
                )
            )
            candidates = [item for item in candidates if item]
            if not candidates:
                flow["identity_hints"] = identity_hints
                hint_count = self._count_operation_identity_hints(identity_hints)
                no_match = hint_count >= 3
                if hint_count >= 3:
                    flow["mismatch_count"] = int(flow.get("mismatch_count", 0)) + 1
                else:
                    flow["mismatch_count"] = 0
                flow["expected_identity_key"] = self._next_identity_question_key(identity_hints, no_match=no_match)
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                return self._build_operation_identity_prompt(
                    identity_hints,
                    no_match=no_match,
                    mismatch_count=int(flow.get("mismatch_count", 0)),
                )

            flow["status"] = "await_target_confirmation"
            flow["candidate_ids"] = [str(item.id) for item in candidates]
            flow["identity_hints"] = identity_hints
            flow["mismatch_count"] = 0
            flow.pop("expected_identity_key", None)
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data

            operation = str(flow.get("operation") or "update")
            operation_label = "変更" if operation == "update" else "キャンセル"
            if len(candidates) == 1:
                return (
                    f"{operation_label}対象の候補は次の予約です。\n"
                    f"{self._format_appointment_brief(candidates[0])}\n"
                    "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
                )

            disambiguation_field = self._choose_disambiguation_field(candidates, identity_hints)
            if disambiguation_field:
                flow["status"] = "await_target_disambiguation"
                flow["disambiguation_field"] = disambiguation_field
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                return self._build_disambiguation_question(disambiguation_field)

            flow["status"] = "await_target_confirmation"
            flow["candidate_ids"] = [str(candidates[0].id)]
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data
            return (
                "同一条件の予約が複数見つかったため、最新の予約を対象候補として確認します。\n"
                f"{self._format_appointment_brief(candidates[0])}\n"
                "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
            )

        if status == "await_target_disambiguation":
            candidate_ids = [str(value) for value in flow.get("candidate_ids", [])]
            candidates = await self._load_operation_candidates_by_ids(candidate_ids)
            if not candidates:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象候補情報が失われました。お手数ですが、もう一度最初から確認させてください。"

            disambiguation_field = str(flow.get("disambiguation_field") or "").strip()
            if not disambiguation_field:
                disambiguation_field = self._choose_disambiguation_field(candidates, dict(flow.get("identity_hints") or {})) or ""
            if not disambiguation_field:
                flow["status"] = "await_target_confirmation"
                flow["candidate_ids"] = [str(candidates[0].id)]
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                return (
                    "同一条件の候補が残っているため、最新の予約を対象候補として確認します。\n"
                    f"{self._format_appointment_brief(candidates[0])}\n"
                    "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
                )

            answer = self._extract_disambiguation_answer(disambiguation_field, user_message)
            if not answer:
                return self._build_disambiguation_question(disambiguation_field)

            narrowed = [
                candidate
                for candidate in candidates
                if self._candidate_matches_disambiguation(candidate, disambiguation_field, answer)
            ]
            if not narrowed:
                return (
                    "ありがとうございます。照合できませんでした。"
                    + self._build_disambiguation_question(disambiguation_field)
                )

            identity_hints = dict(flow.get("identity_hints") or {})
            identity_hints[disambiguation_field] = answer
            flow["identity_hints"] = identity_hints

            if len(narrowed) == 1:
                flow["status"] = "await_target_confirmation"
                flow["candidate_ids"] = [str(narrowed[0].id)]
                flow.pop("disambiguation_field", None)
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                operation = str(flow.get("operation") or "update")
                operation_label = "変更" if operation == "update" else "キャンセル"
                return (
                    f"{operation_label}対象を特定しました。次の予約でよろしいですか？\n"
                    f"{self._format_appointment_brief(narrowed[0])}\n"
                    "よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
                )

            next_field = self._choose_disambiguation_field(narrowed, identity_hints)
            flow["candidate_ids"] = [str(item.id) for item in narrowed]
            if next_field:
                flow["disambiguation_field"] = next_field
                extra_data[self._OP_FLOW_KEY] = flow
                call.extra_data = extra_data
                return self._build_disambiguation_question(next_field)

            narrowed.sort(key=lambda item: item.timestamp or datetime.min, reverse=True)
            flow["status"] = "await_target_confirmation"
            flow["candidate_ids"] = [str(narrowed[0].id)]
            flow.pop("disambiguation_field", None)
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data
            return (
                "同一条件の候補が残っているため、最新の予約を対象候補として確認します。\n"
                f"{self._format_appointment_brief(narrowed[0])}\n"
                "この予約でよろしいでしょうか。よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
            )

        if status == "await_target_confirmation":
            candidate_ids = [str(value) for value in flow.get("candidate_ids", [])]
            selected_id = self._select_candidate_id_from_text(user_message, candidate_ids)

            if not selected_id:
                if self._is_negative(user_message):
                    extra_data.pop(self._OP_FLOW_KEY, None)
                    call.extra_data = extra_data
                    return "承知しました。対象予約を再特定しますので、予約情報を3項目以上教えてください。"
                if len(candidate_ids) == 1 and self._is_affirmative(user_message):
                    selected_id = candidate_ids[0]
                else:
                    return "対象予約を確認できませんでした。この予約でよろしければ「はい」、違う場合は「いいえ」とお知らせください。"

            selected = await self.appointment_repo.get(UUID(selected_id))
            if not selected:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象予約が見つかりませんでした。もう一度指定してください。"

            flow["selected_id"] = selected_id
            operation = flow.get("operation")
            if operation == "cancel":
                return await self._execute_operation_flow_action(
                    call=call,
                    appointment=selected,
                    operation="cancel",
                    pending_changes={},
                    flow=flow,
                    extra_data=extra_data,
                    user_message=user_message,
                )

            flow["status"] = "await_update_payload"
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data
            return (
                "対象予約を確認しました。\n"
                f"{self._format_appointment_brief(selected)}\n"
                "変更内容を教えてください（例: 日時を2026年4月10日10:00に変更、数量を3kgに変更）。"
            )

        if status == "await_update_payload":
            if self._is_negative(user_message):
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "変更手続きを中止しました。必要であれば再度「予約変更」とお伝えください。"

            changes = self._extract_update_changes(user_message)
            if not changes:
                return (
                    "変更内容を解釈できませんでした。"
                    "変更したい項目（日時・住所・数量・カテゴリ）を具体的に教えてください。"
                )

            selected_id = flow.get("selected_id")
            if not selected_id:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象予約情報が失われました。もう一度「予約変更」と伝えてください。"

            selected = await self.appointment_repo.get(UUID(str(selected_id)))
            if not selected:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象予約が見つかりませんでした。もう一度指定してください。"

            summary_parts = []
            if "appointment" in changes:
                new_time = self._parse_appointment_time(changes["appointment"]).strftime("%Y-%m-%d %H:%M")
                old_time = selected.appointment.strftime("%Y-%m-%d %H:%M") if selected.appointment else "-"
                summary_parts.append(f"日時: {old_time} -> {new_time}")
            if "address" in changes:
                summary_parts.append(f"住所: {selected.address or '-'} -> {changes['address']}")
            if "amount" in changes:
                summary_parts.append(f"数量: {selected.amount or '-'} -> {changes['amount']}")
            if "category" in changes:
                summary_parts.append(f"カテゴリ: {selected.category or '-'} -> {changes['category']}")

            flow["status"] = "await_execute_confirmation"
            flow["pending_changes"] = changes
            flow["pending_note"] = user_message
            extra_data[self._OP_FLOW_KEY] = flow
            call.extra_data = extra_data

            return (
                "次の内容で予約を変更します。\n"
                + "\n".join(f"- {part}" for part in summary_parts)
                + "\nこの内容で変更を進めてよろしいでしょうか。よろしければ「はい」、取りやめる場合は「いいえ」とお知らせください。"
            )

        if status == "await_execute_confirmation":
            if self._is_negative(user_message):
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "承知しました。今回の変更/キャンセルは実行しません。"

            if not self._is_affirmative(user_message):
                return "最終確認です。実行する場合は「はい」、取りやめる場合は「いいえ」と回答してください。"

            selected_id = flow.get("selected_id")
            if not selected_id:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象予約情報が失われました。もう一度手続きを開始してください。"

            appointment = await self.appointment_repo.get(UUID(str(selected_id)))
            if not appointment:
                extra_data.pop(self._OP_FLOW_KEY, None)
                call.extra_data = extra_data
                return "対象予約が見つかりませんでした。もう一度指定してください。"

            operation = str(flow.get("operation") or "update")
            pending_changes = dict(flow.get("pending_changes") or {})
            return await self._execute_operation_flow_action(
                call=call,
                appointment=appointment,
                operation=operation,
                pending_changes=pending_changes,
                flow=flow,
                extra_data=extra_data,
                user_message=user_message,
            )

        return None

    async def _resolve_template(self, template_code: str):
        template = await self.prompt_service.get_template(template_code)
        if not template and template_code != "general_appointment":
            raise ValueError(f"Template '{template_code}' not found")
        return template

    def _build_chat_runtime_service(self) -> ChatRuntimeService:
        return ChatRuntimeService(
            self.db,
            call_repo=self.call_repo,
            prompt_service=self.prompt_service,
            normalize_messages=self._normalize_messages,
        )

    def _build_test_session_service(self) -> TestSessionService:
        return TestSessionService(
            self.db,
            call_repo=self.call_repo,
            appointment_repo=self.appointment_repo,
            prompt_service=self.prompt_service,
            extract_appointment=self.extract_appointment,
        )

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> TestSessionStartResponse:
        return await self._build_test_session_service().start_test_session(
            template_code=template_code,
            provider=provider,
            model=model,
            caller_name=caller_name,
        )

    async def finalize_test_session(
        self,
        *,
        call_id: UUID,
        template_code: Optional[str] = None,
        run_extraction: bool = True,
    ) -> TestSessionFinalizeResponse:
        return await self._build_test_session_service().finalize_test_session(
            call_id=call_id,
            template_code=template_code,
            run_extraction=run_extraction,
        )

    async def get_or_create_call(self, call_id: Optional[UUID] = None) -> Call:
        """Get existing call or create a new one."""
        return await self._build_chat_runtime_service().get_or_create_call(call_id)

    async def _setup_chat_context(self, request: ChatRequest, call: Call) -> dict[str, Any]:
        """Setup context for a chat message including templates and LLM client."""
        return await self._build_chat_runtime_service().setup_chat_context(request, call)

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a single chat request and return a response."""
        chat_runtime = self._build_chat_runtime_service()
        call = await chat_runtime.get_or_create_call(request.call_id)
        context = await chat_runtime.setup_chat_context(request, call)

        template = context["template"]
        llm_service = context["llm_service"]
        messages = context["messages"]
        system_prompt = context["system_prompt"]
        prior_assistant_messages = [
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") == "assistant" and str(item.get("content", "")).strip()
        ]

        messages.append({"role": "user", "content": request.message})

        temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
        resp_format, out_schema = self._resolve_chat_response_mode(call, template)
        quota_notice_reason: Optional[str] = None

        operation_flow_response = await self._handle_appointment_operation_flow(call, request.message)
        if operation_flow_response is not None:
            response = operation_flow_response
        elif not settings.google_genai_backend_enabled:
            if not settings.llm_show_quota_notice_as_reply:
                raise ValueError("Gemini backend not configured. Please check backend/.env")
            response = self._build_quota_notice_reply(
                "Gemini backend not configured",
                api_key_missing=True,
            )
            quota_notice_reason = "Gemini backend not configured"
        else:
            try:
                response = await llm_service.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    response_format=resp_format,
                    output_schema=out_schema,
                )
            except LLMRateLimitError as rate_limit_error:
                if not settings.llm_show_quota_notice_as_reply:
                    raise
                quota_notice_reason = str(rate_limit_error)
                response = self._build_quota_notice_reply(quota_notice_reason)
            except Exception as llm_error:
                if not settings.llm_show_quota_notice_as_reply or not self._looks_like_quota_error(str(llm_error)):
                    raise
                quota_notice_reason = str(llm_error)
                response = self._build_quota_notice_reply(quota_notice_reason)

        response = self._sanitize_assistant_response(response)
        response = self._strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )
        messages.append({"role": "assistant", "content": response})
        await chat_runtime.persist_turn(
            call=call,
            user_message=request.message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=quota_notice_reason,
        )

        input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
        total_tokens = count_tokens(input_text) + count_tokens(response)

        return ChatResponse(response=response, call_id=call.id, tokens_used=total_tokens)

    async def process_test_session_operation_turn(
        self,
        *,
        call_id: UUID,
        message: str,
        template_code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TestSessionOperationTurnResponse:
        """Advance test session through operation flow only, without generic LLM fallback."""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message cannot be empty")

        chat_runtime = self._build_chat_runtime_service()
        call = await chat_runtime.get_or_create_call(call_id)
        extra_data = dict(call.extra_data or {})
        messages = self._normalize_messages(extra_data.get("messages"))
        if not messages:
            messages = self._parse_messages_from_transcript(call.transcript)
        prior_assistant_messages = [
            str(item.get("content", "")).strip()
            for item in messages
            if item.get("role") == "assistant" and str(item.get("content", "")).strip()
        ]
        context = {
            "template_code": template_code or extra_data.get("template_code") or "general_appointment",
            "llm_provider": provider or extra_data.get("llm_provider") or "gemini",
            "llm_model": model or extra_data.get("llm_model") or "",
        }

        response = await self._handle_appointment_operation_flow(call, normalized_message)
        if response is None:
            flow = dict((call.extra_data or {}).get(self._OP_FLOW_KEY) or {})
            return TestSessionOperationTurnResponse(
                call_id=call.id,
                handled=False,
                operation=str(flow.get("operation") or "") or None,
                state_status=str(flow.get("status") or "") or None,
                executed=isinstance((call.extra_data or {}).get("operation_execution"), dict),
            )

        response = self._sanitize_assistant_response(response)
        response = self._strip_redundant_opening_greeting(
            response,
            prior_assistant_messages=prior_assistant_messages,
        )

        messages.append({"role": "user", "content": normalized_message})
        messages.append({"role": "assistant", "content": response})
        await chat_runtime.persist_turn(
            call=call,
            user_message=normalized_message,
            assistant_message=response,
            context=context,
            messages=messages,
            quota_notice_reason=None,
        )

        refreshed_extra_data = dict(call.extra_data or {})
        flow = dict(refreshed_extra_data.get(self._OP_FLOW_KEY) or {})
        operation_execution = refreshed_extra_data.get("operation_execution")
        executed = isinstance(operation_execution, dict)
        operation = None
        if executed:
            operation = str(operation_execution.get("operation") or "") or None
        if not operation:
            operation = str(flow.get("operation") or "") or None

        return TestSessionOperationTurnResponse(
            call_id=call.id,
            handled=True,
            response=response,
            operation=operation,
            state_status=str(flow.get("status") or "") or None,
            executed=executed,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Process a chat request and stream the response via SSE."""
        try:
            chat_runtime = self._build_chat_runtime_service()
            call = await chat_runtime.get_or_create_call(request.call_id)

            if not request.call_id:
                yield f"data: {json.dumps({'type': 'call_id', 'call_id': str(call.id)})}\n\n"

            context = await chat_runtime.setup_chat_context(request, call)
            template = context["template"]
            llm_service = context["llm_service"]
            messages = context["messages"]
            system_prompt = context["system_prompt"]
            prior_assistant_messages = [
                str(item.get("content", "")).strip()
                for item in messages
                if item.get("role") == "assistant" and str(item.get("content", "")).strip()
            ]

            messages.append({"role": "user", "content": request.message})

            temperature = request.temperature if request.temperature is not None else (getattr(template, "temperature", None) or 0.7)
            resp_format, out_schema = self._resolve_chat_response_mode(call, template)

            full_response = ""
            quota_notice_reason: Optional[str] = None

            operation_flow_response = await self._handle_appointment_operation_flow(call, request.message)
            if operation_flow_response is not None:
                full_response = operation_flow_response
                yield f"data: {json.dumps({'type': 'content', 'content': full_response})}\n\n"
            elif not settings.google_genai_backend_enabled:
                if not settings.llm_show_quota_notice_as_reply:
                    raise ValueError("Gemini backend not configured. Please check backend/.env")
                quota_notice_reason = "Gemini backend not configured"
                full_response = self._build_quota_notice_reply(quota_notice_reason, api_key_missing=True)
                yield f"data: {json.dumps({'type': 'content', 'content': full_response})}\n\n"
            else:
                try:
                    async for chunk in llm_service.chat_stream(
                        messages=messages,
                        temperature=temperature,
                        response_format=resp_format,
                        output_schema=out_schema,
                    ):
                        candidate_response = f"{full_response}{chunk}"
                        injected_turn_start = self._find_injected_user_turn_start(candidate_response)

                        if injected_turn_start is not None:
                            # Stream only the safe part before model-injected "User: ..." content.
                            safe_response = candidate_response[:injected_turn_start]
                            safe_delta = safe_response[len(full_response):]
                            full_response = safe_response
                            if safe_delta:
                                yield f"data: {json.dumps({'type': 'content', 'content': safe_delta})}\n\n"
                            break

                        full_response = candidate_response
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                except LLMRateLimitError as rate_limit_error:
                    if not settings.llm_show_quota_notice_as_reply:
                        raise
                    quota_notice_reason = str(rate_limit_error)
                    notice = self._build_quota_notice_reply(quota_notice_reason)
                    if full_response:
                        full_response = f"{full_response}\n\n{notice}"
                    else:
                        full_response = notice
                    yield f"data: {json.dumps({'type': 'content', 'content': notice})}\n\n"
                except Exception as llm_error:
                    if not settings.llm_show_quota_notice_as_reply or not self._looks_like_quota_error(str(llm_error)):
                        raise
                    quota_notice_reason = str(llm_error)
                    notice = self._build_quota_notice_reply(quota_notice_reason)
                    if full_response:
                        full_response = f"{full_response}\n\n{notice}"
                    else:
                        full_response = notice
                    yield f"data: {json.dumps({'type': 'content', 'content': notice})}\n\n"

            full_response = self._sanitize_assistant_response(full_response)
            full_response = self._strip_redundant_opening_greeting(
                full_response,
                prior_assistant_messages=prior_assistant_messages,
            )
            messages.append({"role": "assistant", "content": full_response})
            await chat_runtime.persist_turn(
                call=call,
                user_message=request.message,
                assistant_message=full_response,
                context=context,
                messages=messages,
                quota_notice_reason=quota_notice_reason,
                refresh_call=False,
            )

            input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
            total_tokens = count_tokens(input_text) + count_tokens(full_response)

            yield f"data: {json.dumps({'type': 'done', 'call_id': str(call.id), 'tokens_used': total_tokens})}\n\n"

        except ValueError as ve:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ve)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def extract_appointment(self, request: ExtractionRequest) -> ExtractionResponse:
        """Extract appointment details from a completed chat call."""
        try:
            call = await self.call_repo.get(request.call_id)
            if not call:
                raise ValueError("Call not found")

            existing = await self.appointment_repo.get_by_call_id(call.id)
            if existing:
                return ExtractionResponse(
                    success=True,
                    appointment_id=existing.id,
                    extracted_data=existing.extracted_data or {},
                    confidence=1.0,
                    message="已有预约记录，跳过重复提取",
                )

            extra_data = call.extra_data or {}
            operation_execution = extra_data.get("operation_execution")
            if isinstance(operation_execution, dict):
                op_type = str(operation_execution.get("operation") or "").lower()
                appt_id = operation_execution.get("appointment_id")
                if op_type in {"update", "cancel"} and appt_id:
                    try:
                        resolved_id = UUID(str(appt_id))
                    except (TypeError, ValueError):
                        resolved_id = None
                    if resolved_id:
                        return ExtractionResponse(
                            success=True,
                            appointment_id=resolved_id,
                            extracted_data=operation_execution,
                            confidence=1.0,
                            message="检测到本次会话已完成预约变更/取消，跳过新建提取",
                        )

            messages = self._normalize_messages(extra_data.get("messages"))
            if not messages:
                messages = self._parse_messages_from_transcript(call.transcript)
                if messages:
                    extra_data["messages"] = messages
                    call.extra_data = dict(extra_data)
                    await self.db.commit()

            if not messages:
                raise ValueError("No conversation found in call")

            template_code = request.template_code or extra_data.get("template_code", "general_appointment")
            runtime = await resolve_prompt_runtime(
                self.prompt_service,
                template_code=template_code,
                default_code=template_code,
                model_capability="generate",
            )
            template = runtime.template
            if not template:
                raise ValueError(f"Template '{template_code}' not found")

            llm_provider = extra_data.get("llm_provider") or runtime.llm_provider or "gemini"
            llm_model = resolve_generate_model(
                extra_data.get("llm_model"),
                fallback_model=runtime.llm_model,
            )

            llm_service = LLMFactory.create(
                provider=llm_provider,
                api_key=settings.google_api_key,
                model=llm_model,
            )

            extraction_service = ExtractionService(llm_service)
            extraction_result = await extraction_service.extract_appointment(
                conversation=messages,
                template=template,
            )

            raw_data = extraction_result.raw_data or {}
            operation_resolution = await self._try_apply_extracted_operation_request(
                call=call,
                raw_data=raw_data,
                extraction_summary=extraction_result.summary or extraction_result.appointment_content,
                extraction_confidence=extraction_result.confidence,
                extra_data=dict(extra_data),
            )
            if operation_resolution is not None:
                return operation_resolution

            appt_time = self._parse_appointment_time(extraction_result.appointment_time)
            resolved_amount = self._resolve_amount(
                raw_data,
                extraction_result.summary,
                extraction_result.appointment_content,
                call.transcript,
                "\n".join(
                    str(message.get("content", "")).strip()
                    for message in messages
                    if isinstance(message, dict) and str(message.get("content", "")).strip()
                ),
            )
            resolved_address = self._resolve_address(raw_data)
            resolved_extra_request = self._resolve_extra_request(raw_data)
            resolved_category = self._resolve_category(extraction_result.category, raw_data)

            appointment_extra_data = {
                "simulation": bool(extra_data.get("simulation", False)),
                "source": extra_data.get("source", "chat"),
                "simulated_phone": extra_data.get("simulated_phone"),
                "llm_provider": llm_provider,
                "llm_model": llm_model,
            }

            appt_data = dict(
                call_id=call.id,
                timestamp=now_tokyo_naive(),
                caller_name=extraction_result.caller_name or call.caller_name or "Unknown",
                company=extraction_result.company,
                appointment=appt_time,
                category=resolved_category,
                amount=resolved_amount,
                address=resolved_address,
                summary=extraction_result.summary or extraction_result.appointment_content or "提取的预约信息",
                extra_request=resolved_extra_request,
                operation="create",
                prompt_id=template.id if template else None,
                type_name=template.category if template else "general",
                extracted_data=raw_data,
                extra_data=appointment_extra_data,
                raw_messages={
                    "extraction_source": "llm_chat",
                    "template_code": template_code,
                    "confidence": extraction_result.confidence,
                    "conversation": messages,
                    "extracted_data": raw_data,
                },
            )

            appointment = await self.appointment_repo.create(appt_data)

            return ExtractionResponse(
                success=True,
                appointment_id=appointment.id,
                extracted_data=extraction_result.model_dump(),
                confidence=extraction_result.confidence,
                message="预约信息提取成功",
            )
        except Exception as e:
            return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={},
                confidence=0.0,
                message=f"提取失败: {str(e)}",
            )
