from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.dialogflow import (
    DialogflowCreateAppointmentToolRequest,
    DialogflowCreateAppointmentToolResponse,
)
from app.services.prompt_service import PromptService
from app.utils.datetime_utils import now_tokyo_naive, to_tokyo_naive


DEFAULT_DIALOGFLOW_PROMPT_CODE = "base_appointment"


class DialogflowToolService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)

    async def resolve_prompt_id(
        self,
        payload: DialogflowCreateAppointmentToolRequest,
    ) -> UUID | None:
        if payload.prompt_id:
            return payload.prompt_id

        prompt_service = PromptService(self.db)
        prompt_code = payload.prompt_code or DEFAULT_DIALOGFLOW_PROMPT_CODE
        template = await prompt_service.get_template(prompt_code)
        return getattr(template, "id", None) if template else None

    @staticmethod
    def build_summary(payload: DialogflowCreateAppointmentToolRequest) -> str:
        company_name = payload.company_name or "個人"
        amount_text = f"、量は{payload.amount}" if payload.amount else ""
        extra_request = payload.extra_request or "特になし"
        extra_request_text = "" if extra_request == "特になし" else f"。追加要望は{extra_request}"
        appointment_text = to_tokyo_naive(payload.appointment_datetime).strftime("%Y-%m-%d %H:%M")
        return (
            f"{appointment_text}に{payload.pickup_address}で"
            f"{payload.waste_items}{amount_text}の回収予約。"
            f"{company_name}の{payload.contact_name}様からのご依頼"
            f"{extra_request_text}"
        )

    async def create_new_appointment(
        self,
        payload: DialogflowCreateAppointmentToolRequest,
    ) -> DialogflowCreateAppointmentToolResponse:
        if not payload.user_confirmed:
            raise ValueError("user_confirmed must be true before creating an appointment.")

        company_name = payload.company_name or "個人"
        extra_request = payload.extra_request or "特になし"
        summary = self.build_summary(payload)
        prompt_id = await self.resolve_prompt_id(payload)

        appointment = await self.appointment_repo.create(
            {
                "call_id": None,
                "timestamp": now_tokyo_naive(),
                "caller_name": payload.contact_name,
                "company": company_name,
                "appointment": to_tokyo_naive(payload.appointment_datetime),
                "category": payload.waste_items,
                "amount": payload.amount,
                "address": payload.pickup_address,
                "summary": summary,
                "extra_request": extra_request,
                "raw_messages": None,
                "operation": "create",
                "is_handled": False,
                "extra_data": {
                    "source": "dialogflow_playbook",
                    "request_type": payload.request_type,
                    "prompt_code": payload.prompt_code or DEFAULT_DIALOGFLOW_PROMPT_CODE,
                    "playbook_name": payload.playbook_name,
                    "session_id": payload.session_id,
                    "call_sid": payload.call_sid,
                },
                "prompt_id": prompt_id,
                "type_name": "dialogflow_playbook_new_appointment",
                "extracted_data": payload.model_dump(mode="json"),
            }
        )

        return DialogflowCreateAppointmentToolResponse(
            appointment_id=appointment.id,
            summary=summary,
        )
