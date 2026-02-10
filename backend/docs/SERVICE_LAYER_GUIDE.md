# Service 层开发指南

## 📋 概述

Service层已经创建了骨架代码，当SIP服务和日历集成就绪后，您可以在这些骨架基础上实现真实的业务逻辑。

---

## 🏗️ 已创建的Service

### CallService (`app/services/call_service.py`)

**已实现的方法**（可直接使用）:
- ✅ `list_calls()` - 分页查询通话记录
- ✅ `get_call_by_id()` - 根据ID获取通话
- ✅ `get_recent_calls()` - 获取最近的通话

**待实现的方法**（标记为TODO）:
- 🔜 `create_outbound_call()` - 创建外呼
- 🔜 `answer_call()` - 接听来电
- 🔜 `transfer_call()` - 转接通话
- 🔜 `end_call()` - 结束通话

### AppointmentService (`app/services/appointment_service.py`)

**已实现的方法**（可直接使用）:
- ✅ `list_appointments()` - 分页查询预约
- ✅ `get_appointment_by_id()` - 根据ID获取预约
- ✅ `get_upcoming_appointments()` - 获取即将到来的预约

**待实现的方法**（标记为TODO）:
- 🔜 `create_appointment()` - 创建预约
- 🔜 `update_appointment()` - 更新预约
- 🔜 `confirm_appointment()` - 确认预约
- 🔜 `cancel_appointment()` - 取消预约
- 🔜 `reschedule_appointment()` - 重新安排预约

---

## 🔧 如何实现TODO方法

### 步骤 1: 找到TODO方法

所有待实现的方法都标记为：
```python
def method_name(...):
    """
    方法文档
    
    This will be implemented when SIP service is integrated.
    """
    raise NotImplementedError(
        "This requires SIP service integration. "
        "Currently only simulation is supported."
    )
```

### 步骤 2: 实现业务逻辑

替换 `NotImplementedError` 为实际的业务逻辑：

```python
def create_outbound_call(
    self,
    counterpart: str,
    caller_name: Optional[str] = None,
    **kwargs
) -> Call:
    """
    Create an outbound call.
    
    Args:
        counterpart: Phone number to call
        caller_name: Optional caller name
        **kwargs: Additional call parameters
        
    Returns:
        Created call object
    """
    # 1. 创建Call对象
    call = Call(
        id=uuid4(),
        direction=CallDirection.OUTBOUND,
        counterpart=counterpart,
        caller_name=caller_name,
        started_at=datetime.now(timezone.utc),
        status=CallStatus.RINGING,
        handler_type=HandlerType.AI,
        **kwargs
    )
    
    # 2. 调用SIP服务发起呼叫
    # TODO: 集成真实的SIP客户端
    # sip_result = self.sip_client.make_call(counterpart)
    # call.sip_call_id = sip_result.call_id
    
    # 3. 保存到数据库
    self.db.add(call)
    self.db.commit()
    self.db.refresh(call)
    
    return call
```

### 步骤 3: 添加必要的依赖

如果需要SIP客户端或其他服务：

```python
class CallService:
    def __init__(self, db: Session, sip_client=None, llm_client=None):
        self.db = db
        self.repo = CallRepository(db)
        self.sip_client = sip_client  # SIP服务客户端
        self.llm_client = llm_client  # LLM服务客户端
```

---

## 📝 使用示例

### 在API层使用Service

现在API端点已经使用Service层：

```python
# app/api/v1/endpoints/calls.py
from app.services.call_service import CallService

@router.get("")
def list_calls(..., db: Session = Depends(get_db)):
    service = CallService(db)  # ✅ 使用Service层
    items, total = service.list_calls(...)
    return CallListResponse(...)
```

### 在其他Service中使用

```python
# app/services/appointment_service.py
from app.services.call_service import CallService

class AppointmentService:
    def confirm_appointment(self, appointment_id: UUID):
        # 确认预约后，打电话通知客户
        call_service = CallService(self.db)
        call = call_service.create_outbound_call(
            counterpart=appointment.customer_phone,
            caller_name="预约确认系统"
        )
        return appointment
```

---

## ⚠️ 注意事项

1. **不要直接在API层调用Repository**
   - ❌ 错误：`repo = CallRepository(db); repo.get_paginated(...)`
   - ✅ 正确：`service = CallService(db); service.list_calls(...)`

2. **业务逻辑放在Service层**
   - Permission检查
   - 日志记录
   - 事件触发
   - 外部服务调用

3. **保持Repository层纯粹**
   - 只做数据访问
   - 不包含业务逻辑

4. **测试**
   - Service层方法应该有单元测试
   - 模拟外部依赖（SIP客户端等）

---

## 🎯 实现优先级建议

### 高优先级（核心功能）
1. `CallService.create_outbound_call()` - 创建外呼
2. `CallService.answer_call()` - 接听来电
3. `AppointmentService.create_appointment()` - 创建预约

### 中优先级（常用功能）
4. `CallService.transfer_call()` - 转接通话
5. `AppointmentService.confirm_appointment()` - 确认预约
6. `AppointmentService.cancel_appointment()` - 取消预约

### 低优先级（辅助功能）
7. `CallService.end_call()` - 结束通话（可能由SIP自动处理）
8. `AppointmentService.reschedule_appointment()` - 重新安排预约

---

## 📚 参考文档

- [后端开发指南](../docs/DEVELOPMENT_GUIDE.md)
- [分层架构说明](../docs/ARCHITECTURE.md)
- [Call系统设计](../docs/api/call_system_design.md)
- [Appointment系统设计](../docs/api/appointment_system_design.md)

---

**最后更新**: 2026-02-10  
**状态**: 骨架已就绪，等待SIP服务集成
