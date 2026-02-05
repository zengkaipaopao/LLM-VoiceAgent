from datetime import datetime
import json
from fastapi import HTTPException

import re
from sqlalchemy.orm import Session
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointments import AppointmentCreateRequest, AppointmentRecord
from app.models.appointment import Appointment

def parse_japanese_date(dt_str: str) -> datetime:
    """
    Parses various Japanese date formats into a datetime object.
    Supports: 
    - 2025年6月3日午前10時
    - 2025年7月15日午後2时
    - 2025-12-23T10:00:00+09:00
    - 2025-08-20T09:00:00+09:00
    - 2025年7月15日 14:00
    """
    if not dt_str:
        return datetime.now()
        
    # Handle ISO format first
    try:
        if "T" in dt_str:
             clean_str = dt_str.replace("Z", "+00:00")
             return datetime.fromisoformat(clean_str)
    except ValueError:
        pass

    # Handle Japanese text format
    try:
        # Extract digits: year, month, day, hour (minute optional)
        match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", dt_str)
        if match:
            y, m, d = map(int, match.groups())
            
            # AM/PM check
            is_pm = "午後" in dt_str
            is_am = "午前" in dt_str
            
            # Extract time digits
            time_match = re.search(r"(午前|午後)?\s*(\d{1,2})时", dt_str) # Support Japanese '时' as well
            if not time_match:
                time_match = re.search(r"(午前|午後)?\s*(\d{1,2})時", dt_str)
            
            h, minute = 0, 0
            if time_match:
                h = int(time_match.group(2))
                if is_pm and h < 12:
                    h += 12
                elif is_am and h == 12:
                    h = 0
            else:
                # Try HH:MM format after the date
                time_match_hm = re.search(r"(\d{1,2}):(\d{1,2})", dt_str)
                if time_match_hm:
                    h, minute = map(int, time_match_hm.groups())

            return datetime(y, m, d, h, minute)
    except Exception:
        pass
        
    # Fallback to current time if all fails
    return datetime.now()

class AppointmentService:
    async def create_from_conversation(self, payload: AppointmentCreateRequest, db: Session) -> AppointmentRecord:
        if not payload.summary.strip():
            raise HTTPException(status_code=400, detail="预约摘要不能为空")
        
        # Mapping Schema to Model
        appointment_data = payload.model_dump()
        
        # timestamp (Call Arrival Time)
        if payload.timestamp:
            try:
                appointment_data['timestamp'] = datetime.fromisoformat(str(payload.timestamp).replace('Z', '+00:00'))
            except ValueError:
                appointment_data['timestamp'] = datetime.now()
        else:
            appointment_data['timestamp'] = datetime.now()
                
        # appointment (Scheduled Recovery Time) - Parse Japanese text
        appointment_data['appointment'] = parse_japanese_date(payload.appointment)

        # amount (Keep as string with units)
        appointment_data['amount'] = payload.amount if payload.amount else None

        if payload.raw_messages:
             try:
                # If it's already a dict/list (parsed by pydantic or passed as such)
                if isinstance(payload.raw_messages, str):
                    appointment_data['raw_messages'] = json.loads(payload.raw_messages)
                else:
                    appointment_data['raw_messages'] = payload.raw_messages
             except json.JSONDecodeError:
                appointment_data['raw_messages'] = {"raw": payload.raw_messages}
        
        repo = AppointmentRepository(db)
        new_appointment = Appointment(**appointment_data)
        
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)
        
        return new_appointment

    def list_records_paginated(
        self, 
        db: Session,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc",
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None
    ) -> dict:
        repo = AppointmentRepository(db)
        
        dt_start = None
        dt_end = None
        
        if start_date:
            try:
                dt_start = datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
            except ValueError:
                pass
                
        if end_date:
            try:
                dt_end = datetime.fromisoformat(str(end_date).replace('Z', '+00:00'))
            except ValueError:
                pass

        items, total = repo.get_paginated(
            page=page, 
            page_size=pageSize if (page_size == 20 and 'pageSize' in locals()) else page_size, # Fix potential issues if page_size renamed
            sort_by=sort_by, 
            order=order,
            search=search,
            start_date=dt_start,
            end_date=dt_end
        )
        
        # Re-verify page_size usage
        items, total = repo.get_paginated(
            page=page, 
            page_size=page_size, 
            sort_by=sort_by, 
            order=order,
            search=search,
            start_date=dt_start,
            end_date=dt_end
        )
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

appointment_service = AppointmentService()
