"""
Call simulation service for testing.

This service simulates real call scenarios for testing purposes.
In production, these will be triggered by SIP events.
"""
import random
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.call import Call, CallDirection, CallStatus, HandlerType
from app.repositories.call_repository import CallRepository


class CallSimulationService:
    """Service for simulating call scenarios."""
    
    def __init__(self, db: Session):
        self.repo = CallRepository(db)
        self.db = db
    
    def simulate_incoming_call(self, scenario: str = "ai_handled") -> Call:
        """
        Simulate an incoming call with different scenarios.
        
        Args:
            scenario: Type of scenario to simulate
                - "ai_handled": AI successfully handles the call
                - "transferred": AI transfers to human
                - "no_answer": Call not answered
                - "failed": Call failed
                
        Returns:
            Simulated call record
        """
        # Generate realistic test data
        phone_numbers = [
            "+1234567890",
            "+0987654321", 
            "+1111222233",
            "+8613800138000"
        ]
        
        caller_names = [
            "张三",
            "李四",
            "王五",
            "John Smith"
        ]
        
        # Create base call
        now = datetime.utcnow()
        caller_phone = random.choice(phone_numbers)
        receiver_phone = "+1-800-COMPANY"
        
        call = Call(
            id=uuid4(),
            direction=CallDirection.INBOUND,
            counterpart=caller_phone,
            caller_name=random.choice(caller_names),
            started_at=now,
            status=CallStatus.RINGING,
            handler_type=HandlerType.AI,
            sip_call_id=f"sim-{uuid4().hex[:8]}@test.sip.com",
            sip_from=caller_phone,
            sip_to=receiver_phone,
            extra_data={
                "simulation": True,
                "scenario": scenario,
                "simulated_at": datetime.utcnow().isoformat()
            }
        )
        
        # Simulate different scenarios
        if scenario == "ai_handled":
            self._simulate_ai_handled(call, now)
        elif scenario == "transferred":
            self._simulate_transferred(call, now)
        elif scenario == "no_answer":
            self._simulate_no_answer(call, now)
        elif scenario == "failed":
            self._simulate_failed(call, now)
        else:
            self._simulate_ai_handled(call, now)
        
        # Save to database
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        
        return call
    
    def _simulate_ai_handled(self, call: Call, start_time: datetime):
        """Simulate AI successfully handling the call."""
        # Answer after 3-8 seconds
        wait_seconds = random.randint(3, 8)
        call.answered_at = start_time + timedelta(seconds=wait_seconds)
        call.is_answered = True
        call.status = CallStatus.COMPLETED
        
        # Call duration 1-5 minutes
        duration = random.randint(60, 300)
        call.ended_at = call.answered_at + timedelta(seconds=duration)
        call.duration_seconds = duration + wait_seconds
        
        # AI handled successfully
        call.handler_type = HandlerType.AI
        call.ai_confidence = random.randint(85, 100)
        
        # Generate realistic transcript
        call.transcript = """客户: 你好,我想咨询一下你们的产品价格。
AI: 您好!我是智能客服助手。很高兴为您服务。请问您想了解哪款产品的价格呢?
客户: 就是那个新出的智能手表。
AI: 好的,我们最新的智能手表有三个版本:基础版售价1999元,标准版2999元,旗舰版3999元。请问您对哪个版本感兴趣?
客户: 标准版和旗舰版有什么区别?
AI: 标准版包含基本的健康监测和运动追踪功能,而旗舰版额外增加了血氧监测、心电图功能,以及更长的续航时间。
客户: 好的,我了解了,谢谢!
AI: 不客气!如果您还有其他问题,随时欢迎咨询。祝您生活愉快!"""
        
        call.summary = "客户咨询智能手表价格和功能差异,AI成功解答客户疑问。"
    
    def _simulate_transferred(self, call: Call, start_time: datetime):
        """Simulate call transferred to human."""
        # AI answers first
        wait_seconds = random.randint(3, 8)
        call.answered_at = start_time + timedelta(seconds=wait_seconds)
        call.is_answered = True
        
        # AI handles for 1-2 minutes
        ai_duration = random.randint(60, 120)
        call.transferred_at = call.answered_at + timedelta(seconds=ai_duration)
        
        # Then transferred to human
        call.handler_type = HandlerType.TRANSFERRED
        call.transfer_reason = random.choice([
            "客户要求人工客服",
            "需要查询订单详情",
            "复杂问题需要专业解答",
            "客户情绪激动,需要人工安抚"
        ])
        call.ai_confidence = random.randint(60, 80)
        
        # Human handles for 2-5 minutes
        human_duration = random.randint(120, 300)
        total_duration = ai_duration + human_duration
        call.ended_at = call.answered_at + timedelta(seconds=total_duration)
        call.duration_seconds = total_duration + wait_seconds
        call.status = CallStatus.COMPLETED
        
        call.transcript = """客户: 你好,我的订单什么时候能到?
AI: 您好!请问您的订单号是多少?
客户: 我不记得了,你帮我查一下。
AI: 抱歉,我需要订单号才能查询。您可以在订单确认邮件中找到。
客户: 我找不到,你直接用我的手机号查不行吗?
AI: 为了更准确地为您服务,我为您转接人工客服。请稍候...
[转接人工]
人工客服: 您好,我是人工客服小王。我来帮您查询订单。
客户: 好的,我的手机号是...
人工客服: 好的,我查到了您的订单,预计明天下午送达。"""
        
        call.summary = f"客户咨询订单信息,AI无法直接查询,转人工处理。转接原因:{call.transfer_reason}"
    
    def _simulate_no_answer(self, call: Call, start_time: datetime):
        """Simulate unanswered call."""
        # Ring for 30-60 seconds then no answer
        ring_duration = random.randint(30, 60)
        call.ended_at = start_time + timedelta(seconds=ring_duration)
        call.duration_seconds = ring_duration
        call.status = CallStatus.NO_ANSWER
        call.is_answered = False
        call.summary = "客户未接听"
    
    def _simulate_failed(self, call: Call, start_time: datetime):
        """Simulate failed call."""
        # Fail quickly
        call.ended_at = start_time + timedelta(seconds=5)
        call.duration_seconds = 5
        call.status = CallStatus.FAILED
        call.is_answered = False
        call.summary = "呼叫失败"
        call.extra_data["failure_reason"] = random.choice([
            "网络错误",
            "SIP服务器无响应",
            "号码不存在"
        ])
    
    def simulate_batch_calls(self, count: int = 10) -> list[Call]:
        """
        Simulate multiple calls for testing.
        
        Args:
            count: Number of calls to simulate
            
        Returns:
            List of simulated calls
        """
        scenarios = ["ai_handled", "transferred", "no_answer", "failed"]
        weights = [0.6, 0.25, 0.1, 0.05]  # 60% AI handled, 25% transferred, etc.
        
        calls = []
        for _ in range(count):
            scenario = random.choices(scenarios, weights=weights)[0]
            call = self.simulate_incoming_call(scenario)
            calls.append(call)
        
        return calls
