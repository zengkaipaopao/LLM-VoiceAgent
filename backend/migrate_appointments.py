
import json
import uuid
from datetime import datetime
from pathlib import Path
import sys
import os
import re

# Ensure we can import from app
sys.path.append(os.getcwd())

from app.core.database import SessionLocal, engine
from app.models.base import Base # Import Base
from app.models.appointment import Appointment # Import Appointment model
# Import Call model to ensure Base metadata collects all models if needed, though usually import is enough
from app.models.call import Call

def parse_japanese_date(dt_str: str) -> datetime:
    """
    Parses various Japanese date formats into a datetime object.
    Supports: 
    - 2025年6月3日午前10時
    - 2025年7月15日午後2時
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
            
            # Handle time parts
            h, minute = 0, 0
            
            # AM/PM check
            is_pm = "午後" in dt_str
            is_am = "午前" in dt_str
            
            # Extract time digits
            time_match = re.search(r"(午前|午後)?\s*(\d{1,2})時", dt_str)
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
    except Exception as e:
        print(f"Error parsing Japanese date '{dt_str}': {e}")
        
    # Fallback to current time if all fails
    return datetime.now()

def migrate():
    print("Initializing database tables...")
    # Drop table to ensure schema match
    try:
        Appointment.__table__.drop(engine)
        print("Dropped existing appointments table.")
    except Exception as e:
        print(f"Table drop skipped (might not exist): {e}")

    # This will create the appointments table if it doesn't exist
    Base.metadata.create_all(bind=engine)
    print("Tables initialized.")

    # Read JSON
    json_path = Path("data/appointments.json")
    if not json_path.exists():
        print(f"File not found: {json_path}")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    session = SessionLocal()
    count = 0
    skipped = 0
    
    print(f"Found {len(data)} records in JSON.")
    
    for item in data:
        item_id = item.get("id")
        
        # timestamps (Arrival time)
        ts_str = item.get("timestamp")
        if not ts_str or "XX:XX:XX" in ts_str:
             ts_str = ts_str.replace("XX:XX:XX", "12:00:00") if ts_str else datetime.now().isoformat()
        
        try:
            if ts_str.endswith("Z"):
                 ts_str = ts_str.replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            print(f"Skipping invalid arrival timestamp: {ts_str}")
            skipped += 1
            continue

        # appointment (Scheduled time)
        appt_str = item.get("appointment")
        appt_dt = parse_japanese_date(appt_str)

        # amount (preserve as string)
        amount_val = item.get("amount")

        # raw_messages
        raw_msg = item.get("raw_messages")
        if isinstance(raw_msg, str):
            try:
                if raw_msg.strip().startswith("[") or raw_msg.strip().startswith("{"):
                     raw_msg_json = json.loads(raw_msg)
                     raw_msg = raw_msg_json
                else: 
                     raw_msg = {"text": raw_msg}
            except:
                raw_msg = {"text": raw_msg}

        # ID
        try:
            uuid_id = uuid.UUID(item_id) if item_id and len(item_id) == 36 else uuid.uuid4()
        except ValueError:
            uuid_id = uuid.uuid4()

        appt_obj = Appointment(
            id=uuid_id,
            timestamp=ts,
            caller_name=item.get("caller_name", "Unknown"),
            company=item.get("company"),
            appointment=appt_dt,
            category=item.get("category"),
            amount=str(amount_val) if amount_val is not None and amount_val != "" else None,
            address=item.get("address"),
            summary=item.get("summary"),
            extra_request=item.get("extra_request"),
            raw_messages=raw_msg,
            operation=item.get("operation")
        )
        
        session.add(appt_obj)
        count += 1
    
    try:
        session.commit()
        print(f"Successfully migrated {count} records. Skipped {skipped}.")
    except Exception as e:
        session.rollback()
        print(f"Migration failed during commit: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
