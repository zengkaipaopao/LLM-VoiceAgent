"""Matcher for resolving target appointments in update/cancel flows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.appointment import Appointment
from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.services.appointments.parsers import JapaneseAppointmentParser


class AppointmentOperationMatcher:
    """Find existing appointment records using deterministic identity hints."""

    def __init__(self, appointment_repo: AppointmentRepository) -> None:
        self.appointment_repo = appointment_repo

    async def resolve_extracted_operation_target(
        self,
        *,
        call: Call,
        raw_data: dict,
    ) -> Appointment | None:
        target_id_raw = str(raw_data.get("target_appointment_id") or "").strip()
        if target_id_raw:
            try:
                target = await self.appointment_repo.get(UUID(target_id_raw))
            except (TypeError, ValueError):
                target = None
            if target and not JapaneseAppointmentParser.is_cancelled_appointment(target):
                return target

        target_time = JapaneseAppointmentParser.parse_optional_appointment_time(
            raw_data.get("original_appointment_time") or raw_data.get("appointment_time")
        )
        caller_name = JapaneseAppointmentParser.first_non_empty(raw_data.get("caller_name"))
        company = JapaneseAppointmentParser.first_non_empty(raw_data.get("company"))
        contact_phone = JapaneseAppointmentParser.first_non_empty(raw_data.get("contact_phone"))
        query_counterpart = (
            contact_phone if contact_phone and contact_phone.startswith("+") else None
        )

        candidate_rows = await self.appointment_repo.search_operation_candidates_with_call(
            caller_name=caller_name,
            company=company,
            counterpart=query_counterpart,
            appointment_date=target_time.date() if target_time else None,
            limit=50,
        )

        scored_candidates: list[tuple[int, datetime, Appointment]] = []
        for appointment, related_call in candidate_rows:
            if (
                appointment.call_id == call.id
                or JapaneseAppointmentParser.is_cancelled_appointment(appointment)
            ):
                continue
            score = JapaneseAppointmentParser.score_extracted_operation_candidate(
                appointment,
                related_call,
                raw_data=raw_data,
                target_time=target_time,
            )
            threshold = 4 if target_time else 3
            if score >= threshold:
                scored_candidates.append(
                    (score, appointment.timestamp or datetime.min, appointment)
                )

        scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored_candidates[0][2] if scored_candidates else None

    async def find_candidates(
        self,
        call: Call,
        user_message: str,
        *,
        base_hints: dict[str, str] | None = None,
        expected_identity_key: str | None = None,
    ) -> tuple[list[Appointment], dict[str, str]]:
        hints = JapaneseAppointmentParser.collect_operation_identity_hints(
            call,
            user_message,
            base_hints=base_hints,
            expected_identity_key=expected_identity_key,
        )
        if JapaneseAppointmentParser.count_operation_identity_hints(hints) < 3:
            return [], hints

        appointment_date = JapaneseAppointmentParser.parse_hint_date(hints)
        counterpart = JapaneseAppointmentParser.first_non_empty(hints.get("counterpart"))
        query_counterpart = counterpart if counterpart and counterpart.startswith("+") else None

        candidate_rows = await self.appointment_repo.search_operation_candidates_with_call(
            caller_name=JapaneseAppointmentParser.first_non_empty(hints.get("caller_name")),
            company=JapaneseAppointmentParser.first_non_empty(hints.get("company")),
            counterpart=query_counterpart,
            appointment_date=appointment_date,
            limit=30,
        )

        scored_candidates: list[tuple[int, datetime, Appointment]] = []
        for appointment, related_call in candidate_rows:
            score = JapaneseAppointmentParser.score_operation_candidate(
                appointment,
                related_call,
                hints,
            )
            if score >= 3:
                timestamp = appointment.timestamp or datetime.min
                scored_candidates.append((score, timestamp, appointment))

        scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored_candidates[:5]], hints

    async def load_candidates_by_ids(self, candidate_ids: list[str]) -> list[Appointment]:
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
