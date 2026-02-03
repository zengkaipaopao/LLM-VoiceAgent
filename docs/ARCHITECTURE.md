# LLM Voice Agent - 系统架构文档

**版本**: 2.0  
**最后更新**: 2026-02-03  
**状态**: 生产就绪路线图

---

## 📋 目录

1. [系统概述](#系统概述)
2. [核心功能](#核心功能)
3. [技术架构](#技术架构)
4. [系统组件](#系统组件)
5. [数据模型](#数据模型)
6. [API设计](#api设计)
7. [部署架构](#部署架构)
8. [安全性](#安全性)
9. [可观测性](#可观测性)
10. [扩展性](#扩展性)

---

## 系统概述

### 业务目标

LLM Voice Agent是一个**企业级智能语音座席系统**,通过SIP协议实现电话与大语言模型(LLM)的实时对话,并自动提取关键信息记录到数据库中。

### 核心价值

- 🤖 **自动化接听**: 24/7无人值守电话接待
- 📝 **智能提取**: 自动从对话中提取关键业务信息
- 📊 **数据洞察**: 通话记录分析和业务智能
- 🔄 **灵活集成**: 支持多种通信协议和LLM提供商

### 技术特性

- **模块化架构**: 清晰的分层设计,易于维护和扩展
- **供应商解耦**: 适配器模式支持切换通信和AI供应商
- **实时处理**: WebSocket/WebRTC实时音频流处理
- **企业级UI**: 基于IBM Carbon Design System的管理界面

---

## 核心功能

### 1. 智能通话处理

```
┌─────────────┐
│  来电/去电  │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│  SIP网关    │
└──────┬──────┘
       │
       ↓
┌─────────────┐      ┌──────────────┐
│  音频流处理 │─────→│  LLM实时对话 │
└──────┬──────┘      └──────┬───────┘
       │                    │
       ↓                    ↓
┌─────────────┐      ┌──────────────┐
│  语音识别   │      │  意图理解    │
└─────────────┘      └──────────────┘
```

**功能**:
- 呼入/呼出电话管理
- 实时语音识别(ASR)
- 自然语言理解(NLU)
- 文本转语音(TTS)
- 通话录音和转写

### 2. 关键信息提取

```
对话文本
    ↓
┌─────────────────┐
│  LLM结构化提取  │
│  (Function Call)│
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
验证规则    置信度评分
    │         │
    └────┬────┘
         ↓
   ┌──────────┐
   │ 数据库   │
   └──────────┘
```

**提取内容**:
- 客户姓名、联系方式
- 预约时间、服务类型
- 特殊需求、备注信息
- 业务操作(新建/修改/取消)

### 3. 管理仪表盘

**功能模块**:
- 📊 **仪表盘**: 通话统计、成功率、趋势分析
- 📞 **通话记录**: 历史记录查询、录音回放、转写查看
- 📅 **预约管理**: 预约列表、状态跟踪、日历视图
- 💬 **Prompt管理**: 对话模板编辑、版本控制、A/B测试
- ⚙️ **系统设置**: 供应商配置、功能开关、权限管理
- 🧪 **调试工具**: WebSocket/WebRTC实时测试控制台

---

## 技术架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                      │
│  React + TypeScript + Vite + Carbon Design System           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 仪表盘   │  │ 通话管理 │  │ Prompt   │  │ 设置     │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API / WebSocket
┌────────────────────────┴────────────────────────────────────┐
│                        API网关层                              │
│  FastAPI + Uvicorn                                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  认证授权  │  速率限制  │  请求验证  │  CORS        │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                      业务逻辑层 (Services)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 通话流程服务 │  │ LLM编排服务  │  │ 信息提取服务 │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 电话服务     │  │ Prompt服务   │  │ 预约服务     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    数据访问层 (Repositories)                  │
│  Repository Pattern + 依赖注入                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ CallRepo     │  │ PromptRepo   │  │ ApptRepo     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                      数据存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ 对象存储     │     │
│  │ (主数据)     │  │ (缓存/队列)  │  │ (录音文件)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      外部服务集成                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Twilio/SIP   │  │ OpenAI API   │  │ 监控告警     │     │
│  │ (通信)       │  │ (LLM)        │  │ (Prometheus) │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

#### 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **React** | 18.2+ | UI框架 |
| **TypeScript** | 5.0+ | 类型安全 |
| **Vite** | 5.0+ | 构建工具 |
| **Carbon Design** | 1.50+ | 企业级UI组件库 |
| **React Query** | 5.0+ | 数据获取和缓存 |
| **React Router** | 6.0+ | 路由管理 |
| **i18next** | 23.0+ | 国际化(中/英/日) |

#### 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11+ | 编程语言 |
| **FastAPI** | 0.110+ | Web框架 |
| **Pydantic** | 2.0+ | 数据验证 |
| **SQLAlchemy** | 2.0+ | ORM |
| **Alembic** | 1.13+ | 数据库迁移 |
| **Celery** | 5.3+ | 异步任务队列 |
| **Redis** | 7.0+ | 缓存和消息队列 |

#### 基础设施

| 技术 | 用途 |
|------|------|
| **PostgreSQL** | 主数据库 |
| **Redis** | 缓存、会话、消息队列 |
| **Nginx** | 反向代理、负载均衡 |
| **Docker** | 容器化 |
| **Prometheus** | 指标监控 |
| **Grafana** | 可视化 |
| **Loki** | 日志聚合 |

---

## 系统组件

### 前端组件架构

采用**原子化设计(Atomic Design)**模式:

```
src/
├── components/
│   ├── atoms/           # 原子组件(按钮、输入框)
│   │   ├── PageTitle.tsx
│   │   └── PageSubtitle.tsx
│   ├── molecules/       # 分子组件(表单字段、卡片)
│   │   └── LanguageSwitcher.tsx
│   ├── organisms/       # 有机体组件(导航栏、表格)
│   │   ├── PageHeader.tsx
│   │   └── EmptyState.tsx
│   └── templates/       # 模板组件(页面布局)
│       └── PageTemplate.tsx
├── pages/               # 页面组件
│   ├── DashboardPage.tsx
│   ├── CallsPage.tsx
│   ├── AppointmentsPage.tsx
│   ├── PromptsPage.tsx
│   ├── SettingsPage.tsx
│   └── PretrainingPage.tsx
├── features/            # 功能模块
│   └── test/            # 测试控制台
│       └── TestHub.tsx
├── api/                 # API客户端
│   └── client.ts
├── state/               # 状态管理
│   └── store.ts
├── types/               # TypeScript类型
│   └── index.ts
└── config/              # 配置
    ├── i18n.ts          # 国际化配置
    ├── navigation.ts    # 导航配置
    └── theme.ts         # 主题配置
```

### 后端组件架构

采用**分层架构 + 依赖注入**模式:

```
app/
├── api/                 # API路由层
│   ├── __init__.py
│   └── routes.py        # REST API端点定义
├── services/            # 业务逻辑层
│   ├── call_flow.py     # 通话流程编排
│   ├── llm_client.py    # LLM客户端抽象
│   ├── telephony.py     # 电话服务适配器
│   ├── prompt_service.py
│   ├── appointment_service.py
│   ├── chat_service.py
│   ├── realtime_service.py
│   └── tts_service.py
├── repositories/        # 数据访问层
│   ├── base.py          # 基础Repository
│   ├── calls.py
│   ├── prompts.py
│   ├── appointments.py
│   └── models.py        # 数据库模型
├── schemas/             # Pydantic模型
│   ├── calls.py
│   ├── prompts.py
│   ├── appointments.py
│   ├── chat.py
│   └── realtime.py
├── core/                # 核心配置
│   ├── config.py        # 环境配置
│   └── utils.py         # 工具函数
└── main.py              # 应用入口
```

### 关键设计模式

#### 1. Repository模式

```python
# 抽象基类
class BaseRepository(ABC):
    @abstractmethod
    async def create(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        pass
    
    @abstractmethod
    async def list(self, skip: int, limit: int) -> List[T]:
        pass

# 具体实现
class CallRepository(BaseRepository[Call]):
    def __init__(self, db: Session):
        self.db = db
    
    async def create(self, call: CallCreate) -> Call:
        # 实现细节
        pass
```

**优势**:
- 数据访问逻辑集中
- 易于测试(Mock Repository)
- 可以轻松切换存储后端

#### 2. 适配器模式

```python
# 抽象接口
class TelephonyAdapter(ABC):
    @abstractmethod
    async def make_call(self, to: str, from_: str) -> CallSession:
        pass
    
    @abstractmethod
    async def handle_webhook(self, event: WebhookEvent) -> None:
        pass

# Twilio实现
class TwilioAdapter(TelephonyAdapter):
    async def make_call(self, to: str, from_: str) -> CallSession:
        # Twilio特定实现
        pass

# SIP实现
class SipAdapter(TelephonyAdapter):
    async def make_call(self, to: str, from_: str) -> CallSession:
        # SIP特定实现
        pass
```

**优势**:
- 供应商解耦
- 易于切换和测试
- 符合开闭原则

#### 3. 依赖注入

```python
# FastAPI依赖注入
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_call_repository(db: Session = Depends(get_db)) -> CallRepository:
    return CallRepository(db)

# 路由中使用
@router.post("/calls")
async def create_call(
    call: CallCreate,
    repo: CallRepository = Depends(get_call_repository)
):
    return await repo.create(call)
```

---

## 数据模型

### 核心实体关系图

```mermaid
erDiagram
    CALL ||--o{ EXTRACTED_INFO : contains
    CALL ||--o{ APPOINTMENT : creates
    CALL }o--|| PROMPT : uses
    CALL }o--|| AGENT_PROFILE : handled_by
    
    CALL {
        uuid id PK
        string caller_number
        string callee_number
        datetime start_time
        datetime end_time
        text transcript
        string status
        string recording_url
        float duration_seconds
        jsonb metadata
    }
    
    EXTRACTED_INFO {
        uuid id PK
        uuid call_id FK
        string field_name
        string field_value
        float confidence
        datetime extracted_at
    }
    
    APPOINTMENT {
        uuid id PK
        uuid call_id FK
        string customer_name
        string phone
        datetime appointment_time
        string service_type
        string status
        text notes
    }
    
    PROMPT {
        uuid id PK
        string name
        text system_prompt
        jsonb config
        int version
        datetime created_at
    }
    
    AGENT_PROFILE {
        uuid id PK
        string name
        string llm_provider
        string voice_id
        jsonb settings
    }
```

### 数据库Schema

#### calls表

```sql
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_number VARCHAR(20) NOT NULL,
    callee_number VARCHAR(20) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    transcript TEXT,
    status VARCHAR(20) NOT NULL,
    recording_url VARCHAR(500),
    duration_seconds FLOAT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_caller (caller_number),
    INDEX idx_start_time (start_time),
    INDEX idx_status (status)
);
```

#### extracted_info表

```sql
CREATE TABLE extracted_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_call_id (call_id),
    INDEX idx_field_name (field_name)
);
```

#### appointments表

```sql
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    appointment_time TIMESTAMP NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_appointment_time (appointment_time),
    INDEX idx_status (status),
    INDEX idx_phone (phone)
);
```

---

## API设计

### RESTful API端点

#### 通话管理

```
GET    /api/v1/calls              # 获取通话列表
POST   /api/v1/calls/outbound     # 发起呼出
GET    /api/v1/calls/{id}         # 获取通话详情
POST   /api/v1/webhooks/telephony # 接收通话事件
```

#### 预约管理

```
GET    /api/v1/appointments        # 获取预约列表
POST   /api/v1/appointments        # 创建预约
GET    /api/v1/appointments/{id}   # 获取预约详情
PUT    /api/v1/appointments/{id}   # 更新预约
DELETE /api/v1/appointments/{id}   # 取消预约
```

#### Prompt管理

```
GET    /api/v1/prompts             # 获取Prompt列表
POST   /api/v1/prompts             # 创建Prompt
GET    /api/v1/prompts/{id}        # 获取Prompt详情
PUT    /api/v1/prompts/{id}        # 更新Prompt
```

#### 实时会话

```
POST   /api/v1/realtime/session    # 创建实时会话
WS     /ws/realtime                # WebSocket连接
```

### API响应格式

#### 成功响应

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "caller_number": "+8613800138000",
    "status": "completed"
  },
  "meta": {
    "timestamp": "2026-02-03T10:00:00Z",
    "request_id": "req_123456"
  }
}
```

#### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid phone number format",
    "details": {
      "field": "caller_number",
      "constraint": "E.164 format required"
    }
  },
  "meta": {
    "timestamp": "2026-02-03T10:00:00Z",
    "request_id": "req_123456"
  }
}
```

---

## 部署架构

### 开发环境

```
┌─────────────┐
│  开发机器   │
│  ┌────────┐ │
│  │Frontend│ │  :5173
│  └────────┘ │
│  ┌────────┐ │
│  │Backend │ │  :8000
│  └────────┘ │
│  ┌────────┐ │
│  │Postgres│ │  :5432
│  └────────┘ │
└─────────────┘
```

### 生产环境(推荐)

```
                    ┌─────────────┐
                    │  负载均衡   │
                    │  (Nginx)    │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
       │FastAPI  │    │FastAPI  │    │FastAPI  │
       │ 实例1   │    │ 实例2   │    │ 实例3   │
       └────┬────┘    └────┬────┘    └────┬────┘
            │              │              │
            └──────────────┼──────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
       │Postgres │    │ Redis   │    │ Celery  │
       │ (主从)  │    │ Cluster │    │ Workers │
       └─────────┘    └─────────┘    └─────────┘
```

### Docker Compose配置

```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://backend:8000

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/llm_voice
      - REDIS_URL=redis://redis:6379/0

  postgres:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=llm_voice
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  celery:
    build: ./backend
    command: celery -A app.celery worker -l info
    depends_on:
      - redis
      - postgres

volumes:
  postgres_data:
  redis_data:
```

---

## 安全性

### 认证授权

```python
# API Key认证
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key not in settings.VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### 数据加密

- **传输加密**: HTTPS/TLS 1.3
- **存储加密**: 
  - 数据库字段加密(AES-256)
  - 录音文件加密存储
- **敏感信息脱敏**: 
  - 日志中手机号脱敏
  - 前端显示部分隐藏

### 速率限制

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/calls")
@limiter.limit("100/minute")
async def get_calls():
    pass
```

---

## 可观测性

### 监控指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 业务指标
calls_total = Counter('calls_total', 'Total calls', ['status', 'direction'])
call_duration = Histogram('call_duration_seconds', 'Call duration')
active_calls = Gauge('active_calls', 'Currently active calls')

# 技术指标
llm_latency = Histogram('llm_response_seconds', 'LLM response time')
extraction_success = Counter('extraction_success_total', 'Successful extractions')
api_requests = Counter('api_requests_total', 'API requests', ['method', 'endpoint', 'status'])
```

### 日志规范

```python
import structlog

logger = structlog.get_logger()

# 结构化日志
logger.info(
    "call_completed",
    call_id=call.id,
    duration=call.duration_seconds,
    status=call.status,
    extracted_fields=len(extracted_info)
)
```

### 分布式追踪

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

@app.post("/calls")
async def create_call(call: CallCreate):
    with tracer.start_as_current_span("create_call"):
        # 业务逻辑
        pass
```

---

## 扩展性

### 水平扩展

- **无状态设计**: API服务器无状态,可任意扩展
- **会话管理**: 使用Redis存储会话状态
- **数据库**: 读写分离,主从复制

### 垂直扩展

- **异步处理**: 使用Celery处理耗时任务
- **缓存策略**: Redis缓存热点数据
- **CDN**: 静态资源CDN加速

### 微服务演进路径

```
阶段1: 模块化单体 (当前)
    ↓
阶段2: 引入消息队列
    ↓
阶段3: 拆分核心服务
    ├─ 通话服务
    ├─ 信息提取服务
    ├─ LLM编排服务
    └─ 分析服务
    ↓
阶段4: 服务网格
```

---

## 附录

### A. 环境变量配置

```bash
# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/llm_voice
REDIS_URL=redis://localhost:6379/0

# API密钥
OPENAI_API_KEY=sk-xxx
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx

# 应用配置
APP_ENV=production
LOG_LEVEL=INFO
API_KEYS=key1,key2,key3
```

### B. 性能基准

| 指标 | 目标值 |
|------|--------|
| API响应时间(P95) | < 200ms |
| LLM响应时间(P95) | < 2s |
| 并发通话数 | 100+ |
| 数据库查询(P95) | < 50ms |
| 系统可用性 | 99.9% |

### C. 技术债务

- [ ] JSON文件存储迁移到PostgreSQL
- [ ] 添加完整的单元测试覆盖
- [ ] 实现API版本控制
- [ ] 添加GraphQL支持(可选)
- [ ] 实现WebRTC媒体服务器

---

**文档维护**: 此文档应随系统演进持续更新  
**联系方式**: [项目负责人邮箱]  
**许可证**: [项目许可证]
