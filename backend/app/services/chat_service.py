"""
Chat service for LLM orchestrations and extracting data.
"""
import json
from uuid import UUID
from typing import Dict, Any, AsyncIterator, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.call import Call
from app.models.appointment import Appointment
from app.repositories.call_repository import CallRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.services.prompt_service import PromptService
from app.services.extraction_service import ExtractionService
from app.services.llm.factory import LLMFactory
from app.schemas.chat import ChatRequest, ChatResponse, ExtractionRequest, ExtractionResponse
import tiktoken


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class ChatService:
    """Service for handling chat orchestration and appointment extraction."""

    def __init__(self, db: Session):
        self.db = db
        self.call_repo = CallRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.prompt_service = PromptService(db)

    def get_or_create_call(self, call_id: Optional[UUID] = None) -> Call:
        """Get existing call or create a new one."""
        if call_id:
            call = self.call_repo.get(call_id)
            if not call:
                raise ValueError(f"Call {call_id} not found")
            return call
            
        # Create new call
        call_data = {
            "direction": "inbound",
            "counterpart": "chat_user",
            "status": "ongoing",
            "handler_type": "ai"
        }
        return self.call_repo.create(call_data)

    def _setup_chat_context(self, request: ChatRequest, call: Call) -> Tuple[Any, Any, list, str]:
        """Setup context for a chat message including templates and LLM client."""
        template = self.prompt_service.get_template(request.template_code)
        
        # Determine LLM Config
        llm_provider = request.provider or (getattr(template, 'llm_provider', None)) or "gemini"
        llm_model = request.model or (getattr(template, 'llm_model', None)) or settings.default_llm_model

        llm_service = LLMFactory.create(
            provider=llm_provider,
            api_key=settings.google_api_key,
            model=llm_model
        )
        
        # Get historic messages
        extra_data = call.extra_data or {}
        messages = extra_data.get("messages", [])
        
        # Prepare system prompt if required
        system_prompt = ""
        if template:
            system_prompt = self.prompt_service.render_prompt(
                template,
                {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            )
        else:
             # Fallback for development if DB is empty
            if request.template_code == "general_appointment":
                system_prompt = f"""
                You are an AI assistant for appointment booking.
                Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                User wants to book an appointment.
                Extract: name, time, purpose.
                """
            else:
                 raise ValueError(f"Template '{request.template_code}' not found")
            
        if not messages:
            messages.append({"role": "system", "content": system_prompt})
            
        return template, llm_service, messages, system_prompt

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a single chat request and return a response."""
        try:
            call = self.get_or_create_call(request.call_id)
            template, llm_service, messages, system_prompt = self._setup_chat_context(request, call)
            
            messages.append({"role": "user", "content": request.message})
            
            # Extract configurations
            temperature = request.temperature if request.temperature is not None else (getattr(template, 'temperature', None) or 0.7)
            resp_format = getattr(template, 'response_format', None) or "text"
            out_schema = getattr(template, 'output_schema', None)
            
            response = await llm_service.chat_completion(
                messages=messages,
                temperature=temperature,
                response_format=resp_format,
                output_schema=out_schema
            )
            
            messages.append({"role": "assistant", "content": response})
            
            # Prepare update data for Call
            extra_data = call.extra_data or {}
            extra_data["messages"] = messages
            extra_data["template_code"] = request.template_code
            extra_data["llm_provider"] = request.provider or (getattr(template, 'llm_provider', None)) or "gemini"
            extra_data["llm_model"] = request.model or settings.default_llm_model
            
            transcript_update = call.transcript or ""
            transcript_update += f"\n\n用户: {request.message}\n助手: {response}" if transcript_update else f"用户: {request.message}\n助手: {response}"

            # We use an unsafe dict for updating based on the repo interface if it accepts a schema, 
            # here we'll update fields manually then save since the base repo might want a pydantic model for update
            call.extra_data = extra_data
            call.transcript = transcript_update
            
            self.db.commit()
            self.db.refresh(call)

            input_text = request.message + (system_prompt if len(messages) <= 2 else "") + json.dumps(messages)
            total_tokens = count_tokens(input_text) + count_tokens(response)

            return ChatResponse(
                response=response,
                call_id=call.id,
                tokens_used=total_tokens
            )
        except Exception as e:
           raise ValueError(str(e))

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Process a chat request and stream the response via SSE."""
        if not settings.google_api_key:
            yield f"data: {json.dumps({'type': 'error', 'error': 'Google API Key not configured. Please check backend/.env'})}\n\n"
            return
            
        try:
            call = self.get_or_create_call(request.call_id)
            
            # Send initial call ID back immediately for new calls
            if not request.call_id:
               yield f"data: {json.dumps({'type': 'call_id', 'call_id': str(call.id)})}\n\n"
               
            template, llm_service, messages, system_prompt = self._setup_chat_context(request, call)
            messages.append({"role": "user", "content": request.message})
            
            temperature = request.temperature if request.temperature is not None else (getattr(template, 'temperature', None) or 0.7)
            resp_format = getattr(template, 'response_format', None) or "text"
            out_schema = getattr(template, 'output_schema', None)
            
            full_response = ""
            async for chunk in llm_service.chat_stream(
                    messages=messages,
                    temperature=temperature,
                    response_format=resp_format,
                    output_schema=out_schema
                ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                
            messages.append({"role": "assistant", "content": full_response})
            
            extra_data = call.extra_data or {}
            extra_data["messages"] = messages
            extra_data["template_code"] = request.template_code
            extra_data["llm_provider"] = request.provider or (getattr(template, 'llm_provider', None)) or "gemini"
            extra_data["llm_model"] = request.model or settings.default_llm_model
            
            transcript_update = call.transcript or ""
            transcript_update += f"\n\n用户: {request.message}\n助手: {full_response}" if transcript_update else f"用户: {request.message}\n助手: {full_response}"

            call.extra_data = extra_data
            call.transcript = transcript_update
            
            self.db.commit()
            
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
            call = self.call_repo.get(request.call_id)
            if not call:
                raise ValueError("Call not found")
                
            extra_data = call.extra_data or {}
            messages = extra_data.get("messages", [])
            
            if not messages:
                raise ValueError("No conversation found in call")
                
            template_code = request.template_code or extra_data.get("template_code", "general_appointment")
            template = self.prompt_service.get_template(template_code)
            
            if not template:
               raise ValueError(f"Template '{template_code}' not found")
               
            llm_provider = extra_data.get("llm_provider", "gemini")
            llm_model = extra_data.get("llm_model", settings.default_llm_model)

            llm_service = LLMFactory.create(
                provider=llm_provider,
                api_key=settings.google_api_key,
                model=llm_model
            )

            extraction_service = ExtractionService(llm_service)
            extraction_result = await extraction_service.extract_appointment(
                conversation=messages,
                template=template
            )
            
            appt_time = datetime.fromisoformat(extraction_result.appointment_time) if extraction_result.appointment_time else datetime.now()
            
            # Use AppointmentRepo for creating it directly, rather than relying on SQLAlchemy object directly mapping initially.
            appt_data = dict(
                call_id=call.id,
                timestamp=datetime.now(),
                caller_name=extraction_result.caller_name or "Unknown",
                company=extraction_result.company,
                appointment=appt_time,
                category=extraction_result.category,
                summary=extraction_result.summary,
                raw_messages={
                    "extraction_source": "llm_chat",
                    "template_code": template_code,
                    "confidence": extraction_result.confidence,
                    "conversation": messages,
                    "extracted_data": extraction_result.raw_data
                }
            )
            
            appointment = self.appointment_repo.create(appt_data)
            
            return ExtractionResponse(
                success=True,
                appointment_id=appointment.id,
                extracted_data=extraction_result.dict(),
                confidence=extraction_result.confidence,
                message="预约信息提取成功"
            )
        except Exception as e:
           return ExtractionResponse(
                success=False,
                appointment_id=None,
                extracted_data={},
                confidence=0.0,
                message=f"提取失败: {str(e)}"
            )
