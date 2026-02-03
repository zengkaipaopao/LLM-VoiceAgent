# 后端开发规范文档

## 📋 代码规范

### 1. Python代码风格

**遵循PEP 8**

```python
# ✅ 好的命名
class CallService:
    def get_call_by_id(self, call_id: str) -> Call:
        pass

# ❌ 避免的命名
class callservice:
    def GetCallByID(self, callID: str):
        pass
```

**使用类型注解**

```python
# ✅ 完整的类型注解
def create_call(
    db: Session,
    call_data: CallCreate
) -> Call:
    pass

# ❌ 缺少类型注解
def create_call(db, call_data):
    pass
```

---

### 2. 文件组织规范

**每个模块一个文件**

```python
# app/models/call.py - 只包含Call模型
# app/schemas/call.py - 只包含Call相关Schema
# app/repositories/call.py - 只包含Call数据访问
# app/services/call_service.py - 只包含Call业务逻辑
```

**导入顺序**

```python
# 1. 标准库
import os
from datetime import datetime

# 2. 第三方库
from fastapi import APIRouter
from sqlalchemy.orm import Session

# 3. 本地导入
from app.models.call import Call
from app.schemas.call import CallCreate
```

---

### 3. 分层架构规范

**严格遵循分层**

```
API层 → Service层 → Repository层 → Model层
```

**禁止跨层调用**

```python
# ❌ 错误: API直接调用Repository
@router.get("/calls")
def get_calls(db: Session = Depends(get_db)):
    return CallRepository(db).list()  # 错误!

# ✅ 正确: API调用Service,Service调用Repository
@router.get("/calls")
def get_calls(db: Session = Depends(get_db)):
    service = CallService(db)
    return service.list_calls()  # 正确!
```

---

## 🗂️ 目录结构说明

### app/api/ - API路由层

**职责**: 处理HTTP请求和响应

```python
# app/api/v1/calls.py
@router.get("/calls")
async def list_calls(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    service = CallService(db)
    calls = service.list_calls(skip, limit)
    return calls
```

**规范**:
- ✅ 只处理HTTP相关逻辑
- ✅ 参数验证
- ✅ 调用Service层
- ❌ 不包含业务逻辑
- ❌ 不直接访问数据库

---

### app/services/ - 业务逻辑层

**职责**: 实现业务逻辑

```python
# app/services/call_service.py
class CallService:
    def __init__(self, db: Session):
        self.repo = CallRepository(db)
    
    def list_calls(self, skip: int, limit: int):
        # 业务逻辑
        calls = self.repo.list(skip, limit)
        return calls
    
    def create_call_with_prompt(self, call_data, prompt_id):
        # 复杂业务逻辑
        prompt = self.prompt_repo.get(prompt_id)
        call = self.repo.create(call_data)
        # 其他业务处理
        return call
```

**规范**:
- ✅ 包含业务逻辑
- ✅ 调用Repository层
- ✅ 事务管理
- ❌ 不处理HTTP请求
- ❌ 不直接操作SQL

---

### app/repositories/ - 数据访问层

**职责**: 数据库CRUD操作

```python
# app/repositories/call.py
class CallRepository(BaseRepository[Call]):
    def list(self, skip: int = 0, limit: int = 20):
        return self.db.query(Call)\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    def get_by_counterpart(self, counterpart: str):
        return self.db.query(Call)\
            .filter(Call.counterpart == counterpart)\
            .all()
```

**规范**:
- ✅ 只包含数据访问逻辑
- ✅ 使用SQLAlchemy
- ❌ 不包含业务逻辑
- ❌ 不处理HTTP请求

---

### app/models/ - 数据模型层

**职责**: 数据库表定义

```python
# app/models/call.py
class Call(Base):
    __tablename__ = "calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    direction = Column(String(10), nullable=False)
    counterpart = Column(String(50), nullable=False)
    started_at = Column(DateTime, nullable=False)
    
    # 关系
    prompt = relationship("Prompt", back_populates="calls")
```

**规范**:
- ✅ 只定义表结构
- ✅ 定义关系
- ❌ 不包含业务逻辑

---

### app/schemas/ - Pydantic模型

**职责**: 数据验证和序列化

```python
# app/schemas/call.py
class CallBase(BaseModel):
    direction: str
    counterpart: str

class CallCreate(CallBase):
    prompt_id: Optional[UUID] = None

class CallResponse(CallBase):
    id: UUID
    started_at: datetime
    
    class Config:
        from_attributes = True
```

**规范**:
- ✅ 数据验证
- ✅ 序列化/反序列化
- ❌ 不包含业务逻辑

---

## 🔧 开发工作流

### 1. 添加新功能

**步骤**:
1. 创建/更新Model
2. 创建/更新Schema
3. 创建/更新Repository
4. 创建/更新Service
5. 创建/更新API
6. 编写测试

**示例: 添加通话评分功能**

```python
# 1. Model
class Call(Base):
    rating = Column(Integer)  # 新增

# 2. Schema
class CallUpdate(BaseModel):
    rating: Optional[int] = None

# 3. Repository
class CallRepository:
    def update_rating(self, call_id, rating):
        pass

# 4. Service
class CallService:
    def rate_call(self, call_id, rating):
        return self.repo.update_rating(call_id, rating)

# 5. API
@router.patch("/calls/{call_id}/rating")
def rate_call(call_id: UUID, rating: int):
    return service.rate_call(call_id, rating)

# 6. Test
def test_rate_call():
    pass
```

---

### 2. 数据库迁移

```bash
# 1. 修改Model后,创建迁移
alembic revision --autogenerate -m "Add rating to calls"

# 2. 检查生成的迁移文件
cat alembic/versions/xxx_add_rating.py

# 3. 执行迁移
alembic upgrade head

# 4. 回滚(如果需要)
alembic downgrade -1
```

---

### 3. 测试流程

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api/test_calls.py

# 查看覆盖率
pytest --cov=app tests/
```

---

## 📝 命名规范

### 文件命名
- 小写+下划线: `call_service.py`
- 单数形式: `call.py` (不是calls.py)

### 类命名
- 大驼峰: `CallService`
- 描述性: `OpenAIAdapter` (不是OAAdapter)

### 函数命名
- 小写+下划线: `get_call_by_id`
- 动词开头: `create_call`, `update_call`

### 变量命名
- 小写+下划线: `call_data`
- 描述性: `started_at` (不是st)

---

## 🚨 常见错误

### 1. 跨层调用
```python
# ❌ 错误
@router.get("/calls")
def get_calls(db: Session = Depends(get_db)):
    return db.query(Call).all()  # API直接访问数据库

# ✅ 正确
@router.get("/calls")
def get_calls(db: Session = Depends(get_db)):
    service = CallService(db)
    return service.list_calls()
```

### 2. 业务逻辑放错位置
```python
# ❌ 错误: 业务逻辑在API层
@router.post("/calls")
def create_call(call_data: CallCreate):
    # 复杂的业务逻辑...
    if call_data.direction == "inbound":
        # 处理入站逻辑
    pass

# ✅ 正确: 业务逻辑在Service层
class CallService:
    def create_call(self, call_data):
        if call_data.direction == "inbound":
            # 处理入站逻辑
        pass
```

### 3. 缺少类型注解
```python
# ❌ 错误
def get_call(id):
    pass

# ✅ 正确
def get_call(id: UUID) -> Call:
    pass
```

---

## 📚 参考资源

- [FastAPI最佳实践](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [Pydantic文档](https://docs.pydantic.dev/)
- [PEP 8风格指南](https://pep8.org/)
