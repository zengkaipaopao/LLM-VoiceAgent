"""
Chat service for LLM orchestrations and extracting data.
"""
import random
from datetime import datetime
from typing import AsyncIterator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.call_repository import CallRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse,
    TestSessionAppendMessagesResponse,
    TestSessionFinalizeResponse,
    TestSessionOperationTurnResponse,
    TestSessionStartResponse,
)
from app.services.appointments.extraction_applier import AppointmentExtractionApplier
from app.services.appointments.operation_executor import AppointmentOperationExecutor
from app.services.appointments.operation_flow import AppointmentOperationFlowService
from app.services.appointments.operation_matcher import AppointmentOperationMatcher
from app.services.chat_runtime_service import ChatRuntimeService
from app.services.conversation import (
    ConversationOrchestrator,
)
from app.services.conversation import (
    count_tokens as _count_tokens,
)
from app.services.extraction import AppointmentExtractionApplicationService
from app.services.prompt_service import PromptService
from app.services.test_lab import TestSessionOperationTurnService
from app.services.test_session_service import TestSessionService


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Backward-compatible export; implementation lives in conversation domain."""
    return _count_tokens(text, model)


class ChatService:
    """Service for handling chat orchestration and appointment extraction."""
    _OP_FLOW_KEY = "appointment_operation_flow"

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

    @staticmethod
    def _compute_duration_seconds(started_at: Optional[datetime], ended_at: Optional[datetime]) -> int:
        if not started_at or not ended_at:
            return 0
        return max(0, int((ended_at - started_at).total_seconds()))

    async def _handle_appointment_operation_flow(self, call: Call, user_message: str) -> Optional[str]:
        return await self._build_operation_flow_service().handle(call, user_message)

    def _build_chat_runtime_service(self) -> ChatRuntimeService:
        return ChatRuntimeService(
            self.db,
            call_repo=self.call_repo,
            prompt_service=self.prompt_service,
            normalize_messages=ConversationOrchestrator.normalize_messages,
        )

    def _build_conversation_orchestrator(self) -> ConversationOrchestrator:
        return ConversationOrchestrator(
            chat_runtime=self._build_chat_runtime_service(),
            operation_flow_handler=self._handle_appointment_operation_flow,
        )

    def _build_test_session_operation_turn_service(self) -> TestSessionOperationTurnService:
        return TestSessionOperationTurnService(
            chat_runtime=self._build_chat_runtime_service(),
            operation_flow_handler=self._handle_appointment_operation_flow,
            flow_key=self._OP_FLOW_KEY,
            normalize_messages=ConversationOrchestrator.normalize_messages,
            parse_messages_from_transcript=ConversationOrchestrator.parse_messages_from_transcript,
            sanitize_assistant_response=ConversationOrchestrator.sanitize_assistant_response,
            strip_redundant_opening_greeting=ConversationOrchestrator.strip_redundant_opening_greeting,
        )

    def _build_test_session_service(self) -> TestSessionService:
        return TestSessionService(
            self.db,
            call_repo=self.call_repo,
            appointment_repo=self.appointment_repo,
            prompt_service=self.prompt_service,
            extract_appointment=self.extract_appointment,
        )

    def _build_operation_executor(self) -> AppointmentOperationExecutor:
        return AppointmentOperationExecutor(
            self.db,
            appointment_repo=self.appointment_repo,
            flow_key=self._OP_FLOW_KEY,
        )

    def _build_operation_matcher(self) -> AppointmentOperationMatcher:
        return AppointmentOperationMatcher(self.appointment_repo)

    def _build_operation_flow_service(self) -> AppointmentOperationFlowService:
        return AppointmentOperationFlowService(
            appointment_repo=self.appointment_repo,
            matcher=self._build_operation_matcher(),
            executor=self._build_operation_executor(),
            flow_key=self._OP_FLOW_KEY,
        )

    def _build_extraction_applier(self) -> AppointmentExtractionApplier:
        return AppointmentExtractionApplier(
            self.db,
            appointment_repo=self.appointment_repo,
            matcher=self._build_operation_matcher(),
            executor=self._build_operation_executor(),
        )

    def _build_extraction_application_service(self) -> AppointmentExtractionApplicationService:
        return AppointmentExtractionApplicationService(
            self.db,
            call_repo=self.call_repo,
            appointment_repo=self.appointment_repo,
            prompt_service=self.prompt_service,
            extraction_applier=self._build_extraction_applier(),
        )

    async def start_test_session(
        self,
        *,
        template_code: str = "general_appointment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        caller_name: Optional[str] = None,
        mode: str = "text",
    ) -> TestSessionStartResponse:
        return await self._build_test_session_service().start_test_session(
            template_code=template_code,
            provider=provider,
            model=model,
            caller_name=caller_name,
            mode=mode,
        )

    async def append_test_session_messages(
        self,
        *,
        call_id: UUID,
        messages: list[dict[str, str]],
        template_code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TestSessionAppendMessagesResponse:
        return await self._build_test_session_service().append_test_session_messages(
            call_id=call_id,
            messages=messages,
            template_code=template_code,
            provider=provider,
            model=model,
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

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        return await self._build_conversation_orchestrator().process_chat(request)

    async def process_test_session_operation_turn(
        self,
        *,
        call_id: UUID,
        message: str,
        template_code: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> TestSessionOperationTurnResponse:
        return await self._build_test_session_operation_turn_service().process(
            call_id=call_id,
            message=message,
            template_code=template_code,
            provider=provider,
            model=model,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        async for event in self._build_conversation_orchestrator().stream_chat(request):
            yield event

    async def extract_appointment(self, request: ExtractionRequest) -> ExtractionResponse:
        return await self._build_extraction_application_service().extract_appointment(request)
