"""
Appointment simulation service for testing.
"""
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.call import Call, CallDirection, CallStatus, HandlerType
from app.services.call_simulation_service import CallSimulationService

class AppointmentSimulationService:
    """Service for simulating appointment scenarios."""
    
    def __init__(self, db: Session):
        self.db = db
        self.call_service = CallSimulationService(db)
    
    def simulate_appointment(self, scenario: str = "confirmed") -> Appointment:
        """
        Simulate an appointment with different scenarios.
        
        Args:
            scenario: Type of scenario (confirmed, cancelled, pending, emergency)
        """
        # First stimulate a call
        call = self.call_service.simulate_incoming_call(scenario="ai_handled", enable_reviewer=True)
        
        # Base data
        now = datetime.now(timezone.utc)
        appt_date = now + timedelta(days=random.randint(1, 14))
        
        appointment = Appointment(
            id=uuid4(),
            call_id=call.id,
            timestamp=call.started_at,
            caller_name=call.caller_name,
            company=random.choice(["", "个人", "ABC株式会社", "田中商事", "铃木建设"]),
            appointment=appt_date,
            category=random.choice(["粗大ゴミ", "引越し", "基板回収", "不用品回収", "持ち込み"]),
            address=self._generate_random_address(),
            amount=random.choice([f"{random.randint(10, 200)}kg", f"{random.randint(1, 10)}m³"]),
            summary=call.summary,
            operation="create",
            extra_data={
                "simulation": True,
                "scenario": scenario
            }
        )

        # Apply scenario specific logic
        if scenario == "new":
            self._apply_new(appointment)
        elif scenario == "update":
            self._apply_update(appointment)
        elif scenario == "cancel":
            self._apply_cancel(appointment)
        else:
            self._apply_new(appointment)
            
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        
        return appointment

    def _generate_random_address(self) -> str:
        wards = ["新宿区", "渋谷区", "港区", "中央区", "品川区", "目黒区", "世田谷区"]
        areas = ["西新宿", "神宮前", "六本木", "銀座", "大崎", "自由が丘", "二子玉川"]
        return f"東京都{random.choice(wards)}{random.choice(areas)} {random.randint(1, 9)}-{random.randint(1, 20)}-{random.randint(101, 999)}"

    def _apply_new(self, appt: Appointment):
        appt.operation = "create"
        appt.summary = "客户第一次致电，希望能尽快安排上门回收。"
        appt.extra_request = "无"

    def _apply_update(self, appt: Appointment):
        appt.operation = "update"
        appt.summary = "客户致电希望能更改预约时间，推迟到下周。"
        appt.extra_request = "变更前时间：本周五下午"

    def _apply_cancel(self, appt: Appointment):
        appt.operation = "cancel"
        appt.summary = "客户表示不需要服务了，取消预约。"
        appt.extra_request = "无"

    def simulate_batch_appointments(self, count: int = 10) -> list[Appointment]:
        scenarios = ["new", "update", "cancel"]
        weights = [0.7, 0.2, 0.1]
        
        results = []
        for _ in range(count):
            scenario = random.choices(scenarios, weights=weights)[0]
            results.append(self.simulate_appointment(scenario))
        return results

    def clear_test_data(self) -> int:
        from app.models.appointment import Appointment
        deleted = self.db.query(Appointment).filter(
            Appointment.extra_data['simulation'].astext == 'true'
        ).delete(synchronize_session=False)
        self.db.commit()
        return deleted
