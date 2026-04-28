"""State machine for deterministic appointment update/cancel conversations."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.services.appointments.operation_executor import AppointmentOperationExecutor
from app.services.appointments.operation_matcher import AppointmentOperationMatcher
from app.services.appointments.parsers import JapaneseAppointmentParser
from app.services.appointments.presenter import AppointmentBriefPresenter


class AppointmentOperationFlowService:
    """Advance the update/cancel confirmation flow for an appointment call."""

    UUID_PATTERN = re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    )

    def __init__(
        self,
        *,
        appointment_repo: AppointmentRepository,
        matcher: AppointmentOperationMatcher,
        executor: AppointmentOperationExecutor,
        flow_key: str = "appointment_operation_flow",
    ) -> None:
        self.appointment_repo = appointment_repo
        self.matcher = matcher
        self.executor = executor
        self.flow_key = flow_key

    @staticmethod
    def select_candidate_id_from_text(text: str, candidate_ids: list[str]) -> str | None:
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

    @staticmethod
    def build_disambiguation_question(field_key: str) -> str:
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
    def choose_disambiguation_field(
        cls,
        candidates: list[Appointment],
        hints: dict[str, str],
    ) -> str | None:
        if len(candidates) <= 1:
            return None

        def values_for(key: str) -> set[str]:
            values: set[str] = set()
            for item in candidates:
                raw = cls._candidate_value_for_field(item, key)
                normalized = JapaneseAppointmentParser.normalize_match_text(raw)
                if normalized:
                    values.add(normalized)
            return values

        candidate_fields = ["appointment_time", "address", "amount", "company", "caller_name"]
        for field in candidate_fields:
            if len(values_for(field)) <= 1:
                continue
            if field == "company" and JapaneseAppointmentParser.first_non_empty(
                hints.get("company")
            ):
                continue
            if field == "caller_name" and JapaneseAppointmentParser.first_non_empty(
                hints.get("caller_name")
            ):
                continue
            return field
        return None

    @staticmethod
    def _candidate_value_for_field(candidate: Appointment, field_key: str) -> str | None:
        if field_key == "appointment_time":
            return (
                candidate.appointment.strftime("%Y-%m-%d %H:%M")
                if isinstance(candidate.appointment, datetime)
                else None
            )
        if field_key == "address":
            return candidate.address
        if field_key == "amount":
            return candidate.amount
        if field_key == "company":
            return candidate.company
        if field_key == "caller_name":
            return candidate.caller_name
        return None

    @classmethod
    def extract_disambiguation_answer(cls, field_key: str, text: str) -> str | None:
        message = text.strip()
        if not message:
            return None

        if field_key == "appointment_time":
            parsed_dt, has_time = JapaneseAppointmentParser.extract_datetime_parts_from_text(
                message
            )
            if parsed_dt:
                return (
                    parsed_dt.strftime("%Y-%m-%d %H:%M")
                    if has_time
                    else parsed_dt.strftime("%Y-%m-%d")
                )
            return None
        if field_key == "address":
            return JapaneseAppointmentParser.extract_address_from_text(message) or message
        if field_key == "amount":
            return JapaneseAppointmentParser.extract_amount_from_text(message)
        if field_key == "company":
            company, _ = JapaneseAppointmentParser.extract_company_name_pair(message)
            return (
                company
                or JapaneseAppointmentParser.extract_company_hint(message)
                or message
            )
        if field_key == "caller_name":
            _, caller_name = JapaneseAppointmentParser.extract_company_name_pair(message)
            return (
                caller_name
                or JapaneseAppointmentParser.extract_name_hint(message)
                or message
            )
        return message

    @classmethod
    def candidate_matches_disambiguation(
        cls,
        candidate: Appointment,
        field_key: str,
        answer: str,
    ) -> bool:
        answer_text = JapaneseAppointmentParser.normalize_match_text(answer)
        if not answer_text:
            return False

        if field_key == "appointment_time":
            if not isinstance(candidate.appointment, datetime):
                return False
            parsed_dt, has_time = JapaneseAppointmentParser.extract_datetime_parts_from_text(
                answer
            )
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

        candidate_value = cls._candidate_value_for_field(candidate, field_key)
        return JapaneseAppointmentParser.loosely_matches(answer, candidate_value)

    async def handle(self, call: Call, user_message: str) -> str | None:
        extra_data = dict(call.extra_data or {})
        flow = dict(extra_data.get(self.flow_key) or {"status": "idle"})
        status = str(flow.get("status", "idle"))

        if status == "idle":
            return await self._handle_idle(call, user_message, extra_data)
        if status == "await_target_input":
            return await self._handle_target_input(call, user_message, flow, extra_data)
        if status == "await_target_disambiguation":
            return await self._handle_target_disambiguation(
                call,
                user_message,
                flow,
                extra_data,
            )
        if status == "await_target_confirmation":
            return await self._handle_target_confirmation(call, user_message, flow, extra_data)
        if status == "await_update_payload":
            return await self._handle_update_payload(call, user_message, flow, extra_data)
        if status == "await_execute_confirmation":
            return await self._handle_execute_confirmation(call, user_message, flow, extra_data)
        return None

    async def _handle_idle(
        self,
        call: Call,
        user_message: str,
        extra_data: dict,
    ) -> str | None:
        intent = JapaneseAppointmentParser.detect_operation_intent(user_message)
        if intent not in {"update", "cancel"}:
            return None

        candidates, identity_hints = await self.matcher.find_candidates(call, user_message)
        if not candidates:
            hint_count = JapaneseAppointmentParser.count_operation_identity_hints(identity_hints)
            mismatch_count = 1 if hint_count >= 3 else 0
            no_match = hint_count >= 3
            expected_identity_key = JapaneseAppointmentParser.next_identity_question_key(
                identity_hints,
                no_match=no_match,
            )
            extra_data[self.flow_key] = {
                "status": "await_target_input",
                "operation": intent,
                "identity_hints": identity_hints,
                "mismatch_count": mismatch_count,
                "expected_identity_key": expected_identity_key,
            }
            call.extra_data = extra_data
            return JapaneseAppointmentParser.build_operation_identity_prompt(
                identity_hints,
                no_match=no_match,
                mismatch_count=mismatch_count,
            )

        flow = {
            "status": "await_target_confirmation",
            "operation": intent,
            "candidate_ids": [str(item.id) for item in candidates],
        }
        extra_data[self.flow_key] = flow
        call.extra_data = extra_data

        operation_label = "変更" if intent == "update" else "キャンセル"
        if len(candidates) == 1:
            return (
                f"{operation_label}のご依頼ですね。対象候補は次の予約です。\n"
                f"{AppointmentBriefPresenter.format_appointment_brief(candidates[0])}\n"
                "この予約でよろしいでしょうか。よろしければ「はい」、"
                "別の予約なら「いいえ」とお知らせください。"
            )

        return self._confirm_or_disambiguate_candidates(
            call,
            flow=flow,
            extra_data=extra_data,
            candidates=candidates,
            identity_hints=identity_hints,
            latest_fallback_prefix="同一条件の予約が複数見つかったため、最新の予約を対象候補として確認します。",
        )

    async def _handle_target_input(
        self,
        call: Call,
        user_message: str,
        flow: dict,
        extra_data: dict,
    ) -> str:
        selected = await self._load_explicit_uuid_candidate(user_message)
        base_hints = flow.get("identity_hints")
        if not isinstance(base_hints, dict):
            base_hints = {}
        expected_identity_key_raw = str(flow.get("expected_identity_key") or "").strip()
        expected_identity_key = expected_identity_key_raw or None

        if selected:
            candidates = [selected]
            identity_hints = JapaneseAppointmentParser.collect_operation_identity_hints(
                call,
                user_message,
                base_hints=base_hints,
                expected_identity_key=expected_identity_key,
            )
        else:
            candidates, identity_hints = await self.matcher.find_candidates(
                call,
                user_message,
                base_hints=base_hints,
                expected_identity_key=expected_identity_key,
            )

        candidates = [item for item in candidates if item]
        if not candidates:
            flow["identity_hints"] = identity_hints
            hint_count = JapaneseAppointmentParser.count_operation_identity_hints(identity_hints)
            no_match = hint_count >= 3
            flow["mismatch_count"] = int(flow.get("mismatch_count", 0)) + 1 if no_match else 0
            flow["expected_identity_key"] = JapaneseAppointmentParser.next_identity_question_key(
                identity_hints,
                no_match=no_match,
            )
            extra_data[self.flow_key] = flow
            call.extra_data = extra_data
            return JapaneseAppointmentParser.build_operation_identity_prompt(
                identity_hints,
                no_match=no_match,
                mismatch_count=int(flow.get("mismatch_count", 0)),
            )

        flow["status"] = "await_target_confirmation"
        flow["candidate_ids"] = [str(item.id) for item in candidates]
        flow["identity_hints"] = identity_hints
        flow["mismatch_count"] = 0
        flow.pop("expected_identity_key", None)
        extra_data[self.flow_key] = flow
        call.extra_data = extra_data

        operation = str(flow.get("operation") or "update")
        operation_label = "変更" if operation == "update" else "キャンセル"
        if len(candidates) == 1:
            return (
                f"{operation_label}対象の候補は次の予約です。\n"
                f"{AppointmentBriefPresenter.format_appointment_brief(candidates[0])}\n"
                "この予約でよろしいでしょうか。よろしければ「はい」、"
                "別の予約なら「いいえ」とお知らせください。"
            )

        return self._confirm_or_disambiguate_candidates(
            call,
            flow=flow,
            extra_data=extra_data,
            candidates=candidates,
            identity_hints=identity_hints,
            latest_fallback_prefix="同一条件の予約が複数見つかったため、最新の予約を対象候補として確認します。",
        )

    async def _handle_target_disambiguation(
        self,
        call: Call,
        user_message: str,
        flow: dict,
        extra_data: dict,
    ) -> str:
        candidate_ids = [str(value) for value in flow.get("candidate_ids", [])]
        candidates = await self.matcher.load_candidates_by_ids(candidate_ids)
        if not candidates:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象候補情報が失われました。お手数ですが、もう一度最初から確認させてください。"

        disambiguation_field = str(flow.get("disambiguation_field") or "").strip()
        if not disambiguation_field:
            disambiguation_field = self.choose_disambiguation_field(
                candidates,
                dict(flow.get("identity_hints") or {}),
            ) or ""
        if not disambiguation_field:
            return self._fallback_to_latest_candidate(
                call,
                flow=flow,
                extra_data=extra_data,
                candidates=candidates,
                prefix="同一条件の候補が残っているため、最新の予約を対象候補として確認します。",
            )

        answer = self.extract_disambiguation_answer(disambiguation_field, user_message)
        if not answer:
            return self.build_disambiguation_question(disambiguation_field)

        narrowed = [
            candidate
            for candidate in candidates
            if self.candidate_matches_disambiguation(candidate, disambiguation_field, answer)
        ]
        if not narrowed:
            return (
                "ありがとうございます。照合できませんでした。"
                + self.build_disambiguation_question(disambiguation_field)
            )

        identity_hints = dict(flow.get("identity_hints") or {})
        identity_hints[disambiguation_field] = answer
        flow["identity_hints"] = identity_hints

        if len(narrowed) == 1:
            flow["status"] = "await_target_confirmation"
            flow["candidate_ids"] = [str(narrowed[0].id)]
            flow.pop("disambiguation_field", None)
            extra_data[self.flow_key] = flow
            call.extra_data = extra_data
            operation = str(flow.get("operation") or "update")
            operation_label = "変更" if operation == "update" else "キャンセル"
            return (
                f"{operation_label}対象を特定しました。次の予約でよろしいですか？\n"
                f"{AppointmentBriefPresenter.format_appointment_brief(narrowed[0])}\n"
                "よろしければ「はい」、別の予約なら「いいえ」とお知らせください。"
            )

        next_field = self.choose_disambiguation_field(narrowed, identity_hints)
        flow["candidate_ids"] = [str(item.id) for item in narrowed]
        if next_field:
            flow["disambiguation_field"] = next_field
            extra_data[self.flow_key] = flow
            call.extra_data = extra_data
            return self.build_disambiguation_question(next_field)

        narrowed.sort(key=lambda item: item.timestamp or datetime.min, reverse=True)
        return self._fallback_to_latest_candidate(
            call,
            flow=flow,
            extra_data=extra_data,
            candidates=narrowed,
            prefix="同一条件の候補が残っているため、最新の予約を対象候補として確認します。",
        )

    async def _handle_target_confirmation(
        self,
        call: Call,
        user_message: str,
        flow: dict,
        extra_data: dict,
    ) -> str:
        candidate_ids = [str(value) for value in flow.get("candidate_ids", [])]
        selected_id = self.select_candidate_id_from_text(user_message, candidate_ids)

        if not selected_id:
            if JapaneseAppointmentParser.is_negative(user_message):
                extra_data.pop(self.flow_key, None)
                call.extra_data = extra_data
                return (
                    "承知しました。対象予約を再特定しますので、"
                    "予約情報を3項目以上教えてください。"
                )
            if len(candidate_ids) == 1 and JapaneseAppointmentParser.is_affirmative(
                user_message
            ):
                selected_id = candidate_ids[0]
            else:
                return (
                    "対象予約を確認できませんでした。この予約でよろしければ「はい」、"
                    "違う場合は「いいえ」とお知らせください。"
                )

        selected = await self.appointment_repo.get(UUID(selected_id))
        if not selected:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象予約が見つかりませんでした。もう一度指定してください。"

        flow["selected_id"] = selected_id
        operation = flow.get("operation")
        if operation == "cancel":
            return await self.executor.execute(
                call=call,
                appointment=selected,
                operation="cancel",
                pending_changes={},
                flow=flow,
                extra_data=extra_data,
                user_message=user_message,
            )

        flow["status"] = "await_update_payload"
        extra_data[self.flow_key] = flow
        call.extra_data = extra_data
        return (
            "対象予約を確認しました。\n"
            f"{AppointmentBriefPresenter.format_appointment_brief(selected)}\n"
            "変更内容を教えてください（例: 日時を2026年4月10日10:00に変更、数量を3kgに変更）。"
        )

    async def _handle_update_payload(
        self,
        call: Call,
        user_message: str,
        flow: dict,
        extra_data: dict,
    ) -> str:
        if JapaneseAppointmentParser.is_negative(user_message):
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "変更手続きを中止しました。必要であれば再度「予約変更」とお伝えください。"

        changes = JapaneseAppointmentParser.extract_update_changes(user_message)
        if not changes:
            return (
                "変更内容を解釈できませんでした。"
                "変更したい項目（日時・住所・数量・カテゴリ）を具体的に教えてください。"
            )

        selected_id = flow.get("selected_id")
        if not selected_id:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象予約情報が失われました。もう一度「予約変更」と伝えてください。"

        selected = await self.appointment_repo.get(UUID(str(selected_id)))
        if not selected:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象予約が見つかりませんでした。もう一度指定してください。"

        summary_parts = self._build_update_summary_parts(selected, changes)
        flow["status"] = "await_execute_confirmation"
        flow["pending_changes"] = changes
        flow["pending_note"] = user_message
        extra_data[self.flow_key] = flow
        call.extra_data = extra_data

        return (
            "次の内容で予約を変更します。\n"
            + "\n".join(f"- {part}" for part in summary_parts)
            + "\nこの内容で変更を進めてよろしいでしょうか。"
            "よろしければ「はい」、取りやめる場合は「いいえ」とお知らせください。"
        )

    async def _handle_execute_confirmation(
        self,
        call: Call,
        user_message: str,
        flow: dict,
        extra_data: dict,
    ) -> str:
        if JapaneseAppointmentParser.is_negative(user_message):
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "承知しました。今回の変更/キャンセルは実行しません。"

        if not JapaneseAppointmentParser.is_affirmative(user_message):
            return (
                "最終確認です。実行する場合は「はい」、"
                "取りやめる場合は「いいえ」と回答してください。"
            )

        selected_id = flow.get("selected_id")
        if not selected_id:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象予約情報が失われました。もう一度手続きを開始してください。"

        appointment = await self.appointment_repo.get(UUID(str(selected_id)))
        if not appointment:
            extra_data.pop(self.flow_key, None)
            call.extra_data = extra_data
            return "対象予約が見つかりませんでした。もう一度指定してください。"

        operation = str(flow.get("operation") or "update")
        pending_changes = dict(flow.get("pending_changes") or {})
        return await self.executor.execute(
            call=call,
            appointment=appointment,
            operation=operation,
            pending_changes=pending_changes,
            flow=flow,
            extra_data=extra_data,
            user_message=user_message,
        )

    def _confirm_or_disambiguate_candidates(
        self,
        call: Call,
        *,
        flow: dict,
        extra_data: dict,
        candidates: list[Appointment],
        identity_hints: dict[str, str],
        latest_fallback_prefix: str,
    ) -> str:
        disambiguation_field = self.choose_disambiguation_field(candidates, identity_hints)
        if disambiguation_field:
            flow["status"] = "await_target_disambiguation"
            flow["disambiguation_field"] = disambiguation_field
            flow["identity_hints"] = identity_hints
            extra_data[self.flow_key] = flow
            call.extra_data = extra_data
            return self.build_disambiguation_question(disambiguation_field)

        flow["identity_hints"] = identity_hints
        return self._fallback_to_latest_candidate(
            call,
            flow=flow,
            extra_data=extra_data,
            candidates=candidates,
            prefix=latest_fallback_prefix,
        )

    def _fallback_to_latest_candidate(
        self,
        call: Call,
        *,
        flow: dict,
        extra_data: dict,
        candidates: list[Appointment],
        prefix: str,
    ) -> str:
        flow["status"] = "await_target_confirmation"
        flow["candidate_ids"] = [str(candidates[0].id)]
        flow.pop("disambiguation_field", None)
        extra_data[self.flow_key] = flow
        call.extra_data = extra_data
        return (
            f"{prefix}\n"
            f"{AppointmentBriefPresenter.format_appointment_brief(candidates[0])}\n"
            "この予約でよろしいでしょうか。よろしければ「はい」、"
            "別の予約なら「いいえ」とお知らせください。"
        )

    async def _load_explicit_uuid_candidate(self, user_message: str) -> Appointment | None:
        possible_uuid = self.UUID_PATTERN.search(user_message)
        if not possible_uuid:
            return None
        try:
            return await self.appointment_repo.get(UUID(possible_uuid.group(0)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_update_summary_parts(
        selected: Appointment,
        changes: dict[str, str],
    ) -> list[str]:
        summary_parts = []
        if "appointment" in changes:
            new_time = JapaneseAppointmentParser.parse_appointment_time(
                changes["appointment"]
            ).strftime("%Y-%m-%d %H:%M")
            old_time = (
                selected.appointment.strftime("%Y-%m-%d %H:%M")
                if selected.appointment
                else "-"
            )
            summary_parts.append(f"日時: {old_time} -> {new_time}")
        if "address" in changes:
            summary_parts.append(f"住所: {selected.address or '-'} -> {changes['address']}")
        if "amount" in changes:
            summary_parts.append(f"数量: {selected.amount or '-'} -> {changes['amount']}")
        if "category" in changes:
            summary_parts.append(f"カテゴリ: {selected.category or '-'} -> {changes['category']}")
        return summary_parts
