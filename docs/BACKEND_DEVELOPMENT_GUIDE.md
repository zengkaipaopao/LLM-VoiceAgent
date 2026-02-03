# 后端开发指南

**版本**: 1.0  
**目标**: 企业级Python后端开发最佳实践  
**适用人群**: 初级到中级开发者

---

## 📋 目录

1. [项目结构](#项目结构)
2. [开发环境设置](#开发环境设置)
3. [代码规范](#代码规范)
4. [分层架构详解](#分层架构详解)
5. [数据库设计](#数据库设计)
6. [API开发](#api开发)
7. [测试策略](#测试策略)
8. [安全最佳实践](#安全最佳实践)
9. [性能优化](#性能优化)
10. [部署指南](#部署指南)

---

## 项目结构

### 推荐的目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # 应用入口
│   │
│   ├── api/                    # API路由层
│   │   ├── __init__.py
│   │   ├── deps.py            # 依赖注入
│   │   └── v1/                # API版本1
│   │       ├── __init__.py
│   │       ├── calls.py       # 通话相关端点
│   │       ├── appointments.py
│   │       ├── prompts.py
│   │       └── realtime.py
│   │
│   ├── core/                   # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py          # 环境配置
│   │   ├── security.py        # 安全相关
│   │   └── logging.py         # 日志配置
│   │
│   ├── models/                 # 数据库模型
│   │   ├── __init__.py
│   │   ├── base.py            # 基础模型
│   │   ├── call.py
│   │   ├── appointment.py
│   │   └── prompt.py
│   │
│   ├── schemas/                # Pydantic模型
│   │   ├── __init__.py
│   │   ├── call.py
│   │   ├── appointment.py
│   │   └── prompt.py
│   │
│   ├── repositories/           # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── call.py
│   │   └── appointment.py
│   │
│   ├── services/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── call_service.py
│   │   ├── llm_service.py
│   │   ├── extraction_service.py
│   │   └── telephony_service.py
│   │
│   ├── utils/                  # 工具函数
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   └── formatters.py
│   │
│   └── db/                     # 数据库相关
│       ├── __init__.py
│       ├── session.py         # 数据库会话
│       └── init_db.py         # 数据库初始化
│
├── alembic/                    # 数据库迁移
│   ├── versions/
│   └── env.py
│
├── tests/                      # 测试
│   ├── __init__.py
│   ├── conftest.py            # pytest配置
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── e2e/                   # 端到端测试
│
├── scripts/                    # 脚本工具
│   ├── init_db.sh
│   └── seed_data.py
│
├── .env.example               # 环境变量示例
├── pyproject.toml             # Poetry配置
├── Dockerfile
└── docker-compose.yml
```

### 为什么这样组织?

| 目录 | 职责 | 原则 |
|------|------|------|
| **api/** | 处理HTTP请求,参数验证 | 薄层,只做路由和验证 |
| **services/** | 业务逻辑,流程编排 | 核心逻辑,可复用 |
| **repositories/** | 数据访问,CRUD操作 | 数据库解耦 |
| **models/** | 数据库表定义 | ORM模型 |
| **schemas/** | 请求/响应数据结构 | 数据验证 |

---

## 开发环境设置

### 1. 安装依赖管理工具

```bash
# 安装Poetry (推荐)
curl -sSL https://install.python-poetry.org | python3 -

# 或使用pip
pip install poetry
```

### 2. 初始化项目

```bash
cd backend

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

### 3. 配置环境变量

创建 `.env` 文件:

```bash
# 数据库
DATABASE_URL=postgresql://user:password@localhost:5432/llm_voice
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# API密钥
OPENAI_API_KEY=sk-xxx
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx

# 应用配置
APP_ENV=development
DEBUG=True
LOG_LEVEL=DEBUG
SECRET_KEY=your-secret-key-change-in-production

# API安全
API_KEYS=dev_key_1,dev_key_2
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 4. 数据库设置

```bash
# 启动PostgreSQL (Docker)
docker run -d \
  --name postgres \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=llm_voice \
  -p 5432:5432 \
  postgres:16

# 运行数据库迁移
alembic upgrade head
```

### 5. 启动开发服务器

```bash
# 方式1: 直接运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式2: 使用脚本
./scripts/dev.sh
```

---

## 代码规范

### Python代码风格

遵循 **PEP 8** + **Google Python Style Guide**

#### 1. 命名规范

```python
# ✅ 好的命名
class CallService:           # 类名: PascalCase
    def create_call(self):   # 方法: snake_case
        pass

OPENAI_API_KEY = "xxx"       # 常量: UPPER_SNAKE_CASE
max_retries = 3              # 变量: snake_case

# ❌ 避免的命名
class callService:           # 错误: 应该用PascalCase
def CreateCall():            # 错误: 应该用snake_case
MaxRetries = 3               # 错误: 不是常量不要大写
```

#### 2. 类型注解

```python
from typing import Optional, List
from uuid import UUID

# ✅ 始终使用类型注解
def get_call_by_id(call_id: UUID) -> Optional[Call]:
    """获取通话记录"""
    pass

async def list_calls(
    skip: int = 0,
    limit: int = 100
) -> List[Call]:
    """获取通话列表"""
    pass

# ❌ 避免无类型注解
def get_call(id):  # 错误: 缺少类型
    pass
```

#### 3. 文档字符串

```python
def extract_info_from_transcript(
    transcript: str,
    schema: dict
) -> ExtractedInfo:
    """从通话转写中提取结构化信息
    
    Args:
        transcript: 通话转写文本
        schema: 提取字段的JSON Schema
        
    Returns:
        ExtractedInfo: 提取的结构化信息对象
        
    Raises:
        ValidationError: 当提取的数据不符合schema时
        LLMError: 当LLM调用失败时
        
    Example:
        >>> schema = {"name": "string", "phone": "string"}
        >>> info = extract_info_from_transcript(transcript, schema)
        >>> print(info.name)
        "张三"
    """
    pass
```

#### 4. 代码格式化工具

```bash
# 安装工具
poetry add --group dev black isort mypy pylint

# 格式化代码
black app/
isort app/

# 类型检查
mypy app/

# 代码质量检查
pylint app/
```

**配置文件 `pyproject.toml`**:

```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

---

## 分层架构详解

### 架构原则

```
请求流向:
Client → API Layer → Service Layer → Repository Layer → Database

响应流向:
Database → Repository Layer → Service Layer → API Layer → Client
```

### 1. API层 (api/)

**职责**: 
- 接收HTTP请求
- 参数验证
- 调用Service层
- 返回响应

**示例**:

```python
# app/api/v1/calls.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List

from app.schemas.call import CallCreate, CallResponse, CallList
from app.services.call_service import CallService
from app.api.deps import get_call_service

router = APIRouter(prefix="/calls", tags=["calls"])

@router.post("/", response_model=CallResponse, status_code=201)
async def create_call(
    call_data: CallCreate,
    service: CallService = Depends(get_call_service)
) -> CallResponse:
    """创建新的通话记录
    
    - **caller_number**: 主叫号码 (E.164格式)
    - **callee_number**: 被叫号码 (E.164格式)
    - **prompt_id**: 使用的Prompt ID
    """
    try:
        call = await service.create_call(call_data)
        return CallResponse.from_orm(call)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=CallList)
async def list_calls(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    service: CallService = Depends(get_call_service)
) -> CallList:
    """获取通话记录列表
    
    支持分页和状态过滤
    """
    calls = await service.list_calls(skip=skip, limit=limit, status=status)
    total = await service.count_calls(status=status)
    
    return CallList(
        items=calls,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: UUID,
    service: CallService = Depends(get_call_service)
) -> CallResponse:
    """获取单个通话详情"""
    call = await service.get_call_by_id(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return CallResponse.from_orm(call)
```

**关键点**:
- ✅ 使用依赖注入获取Service
- ✅ 详细的文档字符串
- ✅ 明确的响应模型
- ✅ 适当的HTTP状态码
- ✅ 异常处理

### 2. Service层 (services/)

**职责**:
- 业务逻辑实现
- 流程编排
- 调用多个Repository
- 调用外部服务

**示例**:

```python
# app/services/call_service.py
from typing import Optional, List
from uuid import UUID
import structlog

from app.repositories.call import CallRepository
from app.repositories.prompt import PromptRepository
from app.services.telephony_service import TelephonyService
from app.services.llm_service import LLMService
from app.schemas.call import CallCreate
from app.models.call import Call, CallStatus

logger = structlog.get_logger()

class CallService:
    """通话业务逻辑服务"""
    
    def __init__(
        self,
        call_repo: CallRepository,
        prompt_repo: PromptRepository,
        telephony_service: TelephonyService,
        llm_service: LLMService
    ):
        self.call_repo = call_repo
        self.prompt_repo = prompt_repo
        self.telephony = telephony_service
        self.llm = llm_service
    
    async def create_call(self, call_data: CallCreate) -> Call:
        """创建并发起通话
        
        流程:
        1. 验证Prompt存在
        2. 创建通话记录
        3. 发起电话呼叫
        4. 更新通话状态
        """
        logger.info(
            "creating_call",
            caller=call_data.caller_number,
            callee=call_data.callee_number
        )
        
        # 1. 验证Prompt
        prompt = await self.prompt_repo.get_by_id(call_data.prompt_id)
        if not prompt:
            raise ValueError(f"Prompt {call_data.prompt_id} not found")
        
        # 2. 创建通话记录
        call = await self.call_repo.create(call_data)
        
        try:
            # 3. 发起呼叫
            session = await self.telephony.make_call(
                to=call_data.callee_number,
                from_=call_data.caller_number,
                prompt=prompt
            )
            
            # 4. 更新状态
            call.status = CallStatus.RINGING
            call.session_id = session.id
            await self.call_repo.update(call)
            
            logger.info("call_initiated", call_id=call.id)
            return call
            
        except Exception as e:
            # 失败时更新状态
            call.status = CallStatus.FAILED
            await self.call_repo.update(call)
            logger.error("call_failed", call_id=call.id, error=str(e))
            raise
    
    async def list_calls(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Call]:
        """获取通话列表"""
        return await self.call_repo.list(
            skip=skip,
            limit=limit,
            filters={"status": status} if status else None
        )
    
    async def get_call_by_id(self, call_id: UUID) -> Optional[Call]:
        """获取通话详情"""
        return await self.call_repo.get_by_id(call_id)
    
    async def handle_call_completed(self, call_id: UUID, transcript: str):
        """处理通话完成事件
        
        流程:
        1. 更新通话状态
        2. 保存转写文本
        3. 触发信息提取
        """
        call = await self.call_repo.get_by_id(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")
        
        # 更新状态
        call.status = CallStatus.COMPLETED
        call.transcript = transcript
        await self.call_repo.update(call)
        
        # 异步提取信息
        from app.tasks import extract_info_task
        extract_info_task.delay(str(call_id), transcript)
```

**关键点**:
- ✅ 单一职责原则
- ✅ 依赖注入
- ✅ 结构化日志
- ✅ 异常处理
- ✅ 清晰的业务流程

### 3. Repository层 (repositories/)

**职责**:
- 数据库CRUD操作
- 查询构建
- 数据库事务管理

**基础Repository**:

```python
# app/repositories/base.py
from typing import TypeVar, Generic, Optional, List, Type
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """基础Repository,提供通用CRUD操作"""
    
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    async def create(self, obj_in: dict) -> ModelType:
        """创建记录"""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """根据ID获取记录"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None
    ) -> List[ModelType]:
        """获取记录列表"""
        stmt = select(self.model)
        
        # 应用过滤
        if filters:
            for key, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)
        
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update(self, db_obj: ModelType) -> ModelType:
        """更新记录"""
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: UUID) -> bool:
        """删除记录"""
        db_obj = await self.get_by_id(id)
        if db_obj:
            await self.db.delete(db_obj)
            await self.db.commit()
            return True
        return False
```

**具体Repository**:

```python
# app/repositories/call.py
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, func

from app.repositories.base import BaseRepository
from app.models.call import Call, CallStatus

class CallRepository(BaseRepository[Call]):
    """通话记录Repository"""
    
    def __init__(self, db: Session):
        super().__init__(Call, db)
    
    async def get_by_session_id(self, session_id: str) -> Optional[Call]:
        """根据会话ID获取通话"""
        stmt = select(Call).where(Call.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> List[Call]:
        """获取日期范围内的通话"""
        stmt = select(Call).where(
            Call.start_time >= start_date,
            Call.start_time <= end_date
        ).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def count_by_status(self, status: CallStatus) -> int:
        """统计指定状态的通话数量"""
        stmt = select(func.count()).select_from(Call).where(
            Call.status == status
        )
        result = await self.db.execute(stmt)
        return result.scalar()
    
    async def get_active_calls(self) -> List[Call]:
        """获取所有活跃通话"""
        stmt = select(Call).where(
            Call.status.in_([CallStatus.RINGING, CallStatus.IN_PROGRESS])
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
```

**关键点**:
- ✅ 继承基础Repository
- ✅ 特定业务查询方法
- ✅ 使用SQLAlchemy 2.0语法
- ✅ 类型安全

---

## 数据库设计

### 模型定义

```python
# app/models/base.py
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseModel(Base):
    """基础模型,包含通用字段"""
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
```

```python
# app/models/call.py
from enum import Enum
from sqlalchemy import Column, String, Text, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel

class CallStatus(str, Enum):
    """通话状态枚举"""
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"

class Call(BaseModel):
    """通话记录模型"""
    __tablename__ = "calls"
    
    caller_number = Column(String(20), nullable=False, index=True)
    callee_number = Column(String(20), nullable=False)
    session_id = Column(String(100), unique=True, index=True)
    status = Column(SQLEnum(CallStatus), nullable=False, index=True)
    transcript = Column(Text)
    recording_url = Column(String(500))
    duration_seconds = Column(Float)
    metadata = Column(JSONB, default=dict)
    
    def __repr__(self):
        return f"<Call {self.id} {self.caller_number} -> {self.callee_number}>"
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "Add calls table"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

**迁移文件示例**:

```python
# alembic/versions/xxx_add_calls_table.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('caller_number', sa.String(20), nullable=False),
        sa.Column('callee_number', sa.String(20), nullable=False),
        sa.Column('session_id', sa.String(100), unique=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('transcript', sa.Text()),
        sa.Column('recording_url', sa.String(500)),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('metadata', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    # 创建索引
    op.create_index('ix_calls_caller_number', 'calls', ['caller_number'])
    op.create_index('ix_calls_session_id', 'calls', ['session_id'])
    op.create_index('ix_calls_status', 'calls', ['status'])

def downgrade():
    op.drop_table('calls')
```

---

## API开发

### Pydantic Schema设计

```python
# app/schemas/call.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, validator

class CallBase(BaseModel):
    """通话基础Schema"""
    caller_number: str = Field(..., regex=r'^\+?[1-9]\d{1,14}$')
    callee_number: str = Field(..., regex=r'^\+?[1-9]\d{1,14}$')
    
    @validator('caller_number', 'callee_number')
    def validate_phone_number(cls, v):
        """验证电话号码格式"""
        if not v.startswith('+'):
            raise ValueError('Phone number must be in E.164 format')
        return v

class CallCreate(CallBase):
    """创建通话请求"""
    prompt_id: UUID

class CallResponse(CallBase):
    """通话响应"""
    id: UUID
    status: str
    transcript: Optional[str]
    duration_seconds: Optional[float]
    created_at: datetime
    
    class Config:
        orm_mode = True

class CallList(BaseModel):
    """通话列表响应"""
    items: list[CallResponse]
    total: int
    skip: int
    limit: int
```

### 依赖注入

```python
# app/api/deps.py
from typing import Generator
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.config import settings
from app.repositories.call import CallRepository
from app.services.call_service import CallService

# 数据库会话
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Key认证
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key not in settings.API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Repository依赖
def get_call_repository(db: Session = Depends(get_db)) -> CallRepository:
    return CallRepository(db)

# Service依赖
def get_call_service(
    call_repo: CallRepository = Depends(get_call_repository),
    # 其他依赖...
) -> CallService:
    return CallService(call_repo, ...)
```

---

## 测试策略

### 测试金字塔

```
        /\
       /  \      E2E测试 (10%)
      /────\
     /      \    集成测试 (30%)
    /────────\
   /          \  单元测试 (60%)
  /────────────\
```

### 单元测试

```python
# tests/unit/services/test_call_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from app.services.call_service import CallService
from app.models.call import Call, CallStatus

@pytest.fixture
def mock_call_repo():
    return Mock()

@pytest.fixture
def call_service(mock_call_repo):
    return CallService(
        call_repo=mock_call_repo,
        prompt_repo=Mock(),
        telephony_service=Mock(),
        llm_service=Mock()
    )

@pytest.mark.asyncio
async def test_create_call_success(call_service, mock_call_repo):
    """测试成功创建通话"""
    # Arrange
    call_data = CallCreate(
        caller_number="+8613800138000",
        callee_number="+8613900139000",
        prompt_id=uuid4()
    )
    
    expected_call = Call(
        id=uuid4(),
        **call_data.dict(),
        status=CallStatus.INITIATED
    )
    
    mock_call_repo.create = AsyncMock(return_value=expected_call)
    
    # Act
    result = await call_service.create_call(call_data)
    
    # Assert
    assert result.id == expected_call.id
    assert result.status == CallStatus.INITIATED
    mock_call_repo.create.assert_called_once()
```

### 集成测试

```python
# tests/integration/api/test_calls.py
import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.main import app

@pytest.mark.asyncio
async def test_create_call_api(async_client: AsyncClient):
    """测试创建通话API"""
    response = await async_client.post(
        "/api/v1/calls",
        json={
            "caller_number": "+8613800138000",
            "callee_number": "+8613900139000",
            "prompt_id": str(uuid4())
        },
        headers={"X-API-Key": "test_key"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "initiated"
```

---

## 安全最佳实践

### 1. 环境变量管理

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str
    
    # API密钥
    API_KEYS: List[str]
    SECRET_KEY: str
    
    # 外部服务
    OPENAI_API_KEY: str
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### 2. 密码加密

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

### 3. 速率限制

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/calls")
@limiter.limit("100/minute")
async def list_calls():
    pass
```

---

## 性能优化

### 1. 数据库查询优化

```python
# ❌ N+1查询问题
calls = await call_repo.list()
for call in calls:
    prompt = await prompt_repo.get_by_id(call.prompt_id)  # N次查询

# ✅ 使用JOIN
from sqlalchemy.orm import joinedload

stmt = select(Call).options(joinedload(Call.prompt))
calls = await db.execute(stmt)
```

### 2. 缓存策略

```python
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379)

@lru_cache(maxsize=100)
def get_prompt_by_id(prompt_id: str):
    # 先查缓存
    cached = redis_client.get(f"prompt:{prompt_id}")
    if cached:
        return json.loads(cached)
    
    # 查数据库
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    
    # 写缓存
    redis_client.setex(
        f"prompt:{prompt_id}",
        3600,  # 1小时过期
        json.dumps(prompt.dict())
    )
    
    return prompt
```

### 3. 异步任务

```python
# app/tasks.py
from celery import Celery

celery_app = Celery('tasks', broker='redis://localhost:6379/1')

@celery_app.task
def extract_info_task(call_id: str, transcript: str):
    """异步提取信息任务"""
    # 耗时操作
    info = extract_info(transcript)
    save_to_db(call_id, info)
```

---

## 部署指南

### Docker化

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装Poetry
RUN pip install poetry

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 安装依赖
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# 复制代码
COPY . .

# 运行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 健康检查

```python
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "database": await check_database(),
        "redis": await check_redis()
    }
```

---

## 总结

### 开发检查清单

- [ ] 代码遵循PEP 8规范
- [ ] 所有函数有类型注解
- [ ] 关键函数有文档字符串
- [ ] 使用依赖注入
- [ ] 分层架构清晰
- [ ] 编写单元测试
- [ ] 使用结构化日志
- [ ] 环境变量配置
- [ ] API有认证授权
- [ ] 数据库有索引
- [ ] 敏感信息加密
- [ ] 添加监控指标

### 下一步

1. 阅读 [API开发指南](./API_GUIDE.md)
2. 阅读 [数据库设计指南](./DATABASE_GUIDE.md)
3. 查看 [部署手册](./DEPLOYMENT.md)
