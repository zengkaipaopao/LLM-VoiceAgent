"""
Chat API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncIterator
import json
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ExtractionRequest,
    ExtractionResponse
)
from app.models.call import Call
from app.models.appointment import Appointment
from app.services.llm import LLMFactory
from app.services.prompt_service import PromptService
from app.services.extraction_service import ExtractionService
import tiktoken

router = APIRouter()

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens for a given text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with LLM.
    
    Creates or updates a Call record and returns AI response.
    """
    try:
        # Get prompt template
        prompt_service = PromptService(db)
        template = prompt_service.get_template(request.template_code)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{request.template_code}' not found"
            )
        
        # Determine LLM Config
        # Priority: Request Param > Template Config > Default
        llm_provider = request.provider or (template.llm_provider if template else "gemini")
        llm_model = request.model or (template.llm_model if template else settings.default_llm_model)
        temperature = request.temperature if request.temperature is not None else (template.temperature if template else 0.7)

        # Create LLM service
        llm_service = LLMFactory.create(
            provider=llm_provider,
            api_key=settings.google_api_key,
            model=llm_model
        )
        
        # Get or create Call record
        if request.call_id:
            call = db.query(Call).filter(Call.id == request.call_id).first()
            if not call:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Call not found"
                )
        else:
            # Create new call
            call = Call(
                direction="inbound",
                counterpart="chat_user",
                status="ongoing",
                handler_type="ai"
            )
            db.add(call)
            db.flush()
        
        # Get conversation history from extra_data
        extra_data = call.extra_data or {}
        messages = extra_data.get("messages", [])
        
        # Render system prompt
        system_prompt = prompt_service.render_prompt(
            template,
            {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        )
        
        # Build messages
        if not messages:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": request.message})
        
        # Get LLM response
        response = await llm_service.chat_completion(
            messages=messages,
            temperature=request.temperature,
            response_format=template.response_format if template else "text",
            output_schema=template.output_schema if template else None
        )
        
        # Add assistant response to messages
        messages.append({"role": "assistant", "content": response})
        
        # Update Call record
        extra_data["messages"] = messages
        extra_data["template_code"] = request.template_code
        extra_data["llm_provider"] = request.provider
        extra_data["llm_model"] = request.model or settings.default_llm_model
        
        call.extra_data = extra_data
        
        # Update transcript
        if call.transcript:
            call.transcript += f"\n\n用户: {request.message}\n助手: {response}"
        else:
            call.transcript = f"用户: {request.message}\n助手: {response}"
        
        db.commit()
        db.refresh(call)
        
        # Calculate tokens
        input_text = request.message + (system_prompt if not messages else "") + json.dumps(messages)
        output_text = response
        total_tokens = count_tokens(input_text) + count_tokens(output_text)

        return ChatResponse(
            response=response,
            call_id=call.id,
            tokens_used=total_tokens
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Stream chat with LLM using Server-Sent Events.
    """
    async def event_generator() -> AsyncIterator[str]:
        try:
            # Check API Key
            if not settings.google_api_key:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Google API Key not configured. Please check backend/.env'})}\n\n"
                return

            # Get prompt template
            prompt_service = PromptService(db)
            template = prompt_service.get_template(request.template_code)
            
            if not template:
                # Fallback for development if DB is empty
                if request.template_code == "general_appointment":
                    template = """
                    You are an AI assistant for appointment booking.
                    Current time: {{current_time}}
                    User wants to book an appointment.
                    Extract: name, time, purpose.
                    """
                else:
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Template {request.template_code} not found'})}\n\n"
                    return
            
            # Determine LLM Config
            # Priority: Request Param > Template Config > Default
            llm_provider = request.provider or (template.llm_provider if template else "gemini")
            llm_model = request.model or (template.llm_model if template else settings.default_llm_model)
            temperature = request.temperature if request.temperature is not None else (template.temperature if template else 0.7)

            # Create LLM service
            llm_service = LLMFactory.create(
                provider=llm_provider,
                api_key=settings.google_api_key,
                model=llm_model
            )
            
            # Get or create Call record
            if request.call_id:
                call = db.query(Call).filter(Call.id == request.call_id).first()
                if not call:
                    yield f"data: {json.dumps({'error': 'Call not found'})}\n\n"
                    return
            else:
                call = Call(
                    direction="inbound",
                    counterpart="chat_user",
                    status="ongoing",
                    handler_type="ai"
                )
                db.add(call)
                db.flush()
                
                # Send call_id to client
                yield f"data: {json.dumps({'type': 'call_id', 'call_id': str(call.id)})}\n\n"
            
            # Get conversation history
            extra_data = call.extra_data or {}
            messages = extra_data.get("messages", [])
            
            # Render system prompt
            system_prompt = prompt_service.render_prompt(
                template,
                {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            )
            
            # Build messages
            if not messages:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": request.message})
            
            # Stream LLM response
            full_response = ""
            try:
                async for chunk in llm_service.chat_stream(
                    messages=messages,
                    temperature=request.temperature,
                    response_format=template.response_format if template else "text",
                    output_schema=template.output_schema if template else None
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            except Exception as e:
                # Log error if needed
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                raise e
            
            # Add to messages
            messages.append({"role": "assistant", "content": full_response})
            
            # Update Call record
            extra_data["messages"] = messages
            extra_data["template_code"] = request.template_code
            extra_data["llm_provider"] = request.provider
            extra_data["llm_model"] = request.model or settings.default_llm_model
            
            call.extra_data = extra_data
            
            # Update transcript
            if call.transcript:
                call.transcript += f"\n\n用户: {request.message}\n助手: {full_response}"
            else:
                call.transcript = f"用户: {request.message}\n助手: {full_response}"
            
            db.commit()
            
            # Calculate tokens
            input_text = request.message + (system_prompt if not messages else "") + json.dumps(messages)
            output_text = full_response
            total_tokens = count_tokens(input_text) + count_tokens(output_text)

            # Send done event with tokens
            yield f"data: {json.dumps({'type': 'done', 'call_id': str(call.id), 'tokens_used': total_tokens})}\n\n"
            
        except Exception as e:
            print(f"DEBUG: Initial Error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.post("/extract", response_model=ExtractionResponse)
async def extract_appointment(
    request: ExtractionRequest,
    db: Session = Depends(get_db)
):
    """
    Extract appointment information from conversation.
    """
    try:
        # Get Call record
        call = db.query(Call).filter(Call.id == request.call_id).first()
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        # Get conversation messages
        extra_data = call.extra_data or {}
        messages = extra_data.get("messages", [])
        
        if not messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No conversation found in call"
            )
        
        # Get template
        prompt_service = PromptService(db)
        template_code = request.template_code or extra_data.get("template_code", "general_appointment")
        template = prompt_service.get_template(template_code)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_code}' not found"
            )
        
        # Create LLM service
        llm_provider = extra_data.get("llm_provider", "gemini")
        llm_model = extra_data.get("llm_model", settings.default_llm_model)
        
        llm_service = LLMFactory.create(
            provider=llm_provider,
            api_key=settings.google_api_key,
            model=llm_model
        )
        
        # Extract appointment
        extraction_service = ExtractionService(llm_service)
        extraction = await extraction_service.extract_appointment(
            conversation=messages,
            template=template
        )
        
        # Create Appointment record
        appointment = Appointment(
            call_id=call.id,
            timestamp=datetime.now(),
            caller_name=extraction.caller_name or "Unknown",
            company=extraction.company,
            appointment=datetime.fromisoformat(extraction.appointment_time) if extraction.appointment_time else datetime.now(),
            category=extraction.category,
            summary=extraction.summary,
            raw_messages={
                "extraction_source": "llm_chat",
                "template_code": template_code,
                "confidence": extraction.confidence,
                "conversation": messages,
                "extracted_data": extraction.raw_data
            }
        )
        
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        
        return ExtractionResponse(
            success=True,
            appointment_id=appointment.id,
            extracted_data=extraction.dict(),
            confidence=extraction.confidence,
            message="预约信息提取成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ExtractionResponse(
            success=False,
            appointment_id=None,
            extracted_data={},
            confidence=0.0,
            message=f"提取失败: {str(e)}"
        )
