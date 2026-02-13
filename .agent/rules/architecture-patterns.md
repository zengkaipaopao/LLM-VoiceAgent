---
trigger: always_on
---

# 架构模式和设计原则

## 核心架构原则

### 1. 分层架构 (Layered Architecture)

**强制执行以下分层**:
```
API 层 (routes.py)
    ↓
Service 层 (services/)
    ↓
Repository 层 (repositories/)
    ↓
数据库/外部服务
```

**规则**:
- ❌ **禁止跨层访问**: API 层不能直接访问 Repository
- ❌ **禁止反向依赖**: Repository 不能调用 Service
- ✅ **依赖注入**: 使用 FastAPI 的 `Depends()` 注入依赖

### 2. Repository 模式

**所有数据访问必须通过 Repository**:

```python
# ✅ 正确: 使用 Repository
class CallService:
    def __init__(self, call_repo: CallRepository):
        self.call_repo = call_repo
    
    async def get_call(self, call_id: UUID) -> Call:
        return await self.call_repo.get_by_id(call_id)

# ❌ 错误: Service 直接操作数据库
class CallService:
    async def get_call(self, call_id: UUID) -> Call:
        return db.query(Call).filter(Call.id == call_id).first()
```

**Repository 必须继承 `BaseRepository`**:
- 实现标准 CRUD 方法: `create`, `get_by_id`, `list`, `update`, `delete`
- 复杂查询封装为专用方法 (例: `get_active_calls_by_date_range`)

### 3. Adapter 模式

**外部服务集成必须使用 Adapter**:

```python
# 定义抽象接口
class LLMAdapter(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        pass

# 具体实现
class OpenAIAdapter(LLMAdapter):
    async def generate_response(self, prompt: str) -> str:
        # OpenAI 特定实现
        pass

class GeminiAdapter(LLMAdapter):
    async def generate_response(self, prompt: str) -> str:
        # Gemini 特定实现
        pass
```

**适用场景**:
- LLM 提供商 (OpenAI, Gemini, Claude)
- 通信服务 (Twilio, SIP)
- 存储服务 (S3, GCS)

### 4. 依赖注入 (Dependency Injection)

**使用 FastAPI 的依赖注入系统**:

```python
# 定义依赖
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_call_repository(db: Session = Depends(get_db)) -> CallRepository:
    return CallRepository(db)

# 在路由中注入
@router.get("/calls/{call_id}")
async def get_call(
    call_id: UUID,
    repo: CallRepository = Depends(get_call_repository)
):
    return await repo.get_by_id(call_id)
```

**优势**:
- 易于测试 (可以 Mock 依赖)
- 解耦组件
- 集中管理生命周期

---

## 前端架构模式

### 1. Atomic Design

**组件分类**:
- **Atoms** (原子): 最小单元,不可再分 (例: `Button`, `Input`, `PageTitle`)
- **Molecules** (分子): 简单组合 (例: `SearchBar`, `FormField`)
- **Organisms** (有机体): 复杂组合 (例: `Header`, `DataTable`, `CallCard`)
- **Templates** (模板): 页面布局 (例: `PageTemplate`)
- **Pages** (页面): 具体页面 (例: `DashboardPage`, `CallsPage`)

**文件组织**:
```
src/components/
├── atoms/
│   ├── PageTitle.tsx
│   └── StatusBadge.tsx
├── molecules/
│   └── LanguageSwitcher.tsx
├── organisms/
│   ├── PageHeader.tsx
│   └── CallDataTable.tsx
└── templates/
    └── PageTemplate.tsx
```

### 2. Container/Presentational 分离

**Presentational 组件** (展示组件):
- 只负责 UI 渲染
- 通过 props 接收数据
- 无状态或只有 UI 状态

```typescript
// ✅ Presentational
interface CallCardProps {
  call: CallRecord;
  onSelect: () => void;
}

export const CallCard: React.FC<CallCardProps> = ({ call, onSelect }) => {
  return (
    <Tile onClick={onSelect}>
      <h3>{call.callerNumber}</h3>
      <p>{call.status}</p>
    </Tile>
  );
};
```

**Container 组件** (容器组件):
- 处理业务逻辑
- 管理状态
- 调用 API

```typescript
// ✅ Container
export const CallListContainer: React.FC = () => {
  const { data: calls, isLoading } = useQuery('calls', fetchCalls);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  
  return (
    <CallList 
      calls={calls} 
      isLoading={isLoading}
      onSelect={setSelectedId}
    />
  );
};
```

### 3. Custom Hooks

**复用逻辑提取为 Hooks**:

```typescript
// ✅ 自定义 Hook
function useWebSocket(url: string) {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  
  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (event) => {
      setMessages(prev => [...prev, JSON.parse(event.data)]);
    };
    setSocket(ws);
    return () => ws.close();
  }, [url]);
  
  return { socket, messages };
}

// 在组件中使用
function ChatComponent() {
  const { socket, messages } = useWebSocket('ws://localhost:8000/ws');
  // ...
}
```

---

## SOLID 原则

### S - 单一职责原则 (Single Responsibility)
- 每个类/函数只做一件事
- 修改的理由只有一个

```python
# ❌ 错误: 职责混乱
class CallHandler:
    async def process_call(self, call_data):
        # 验证数据
        if not call_data.phone:
            raise ValueError()
        # 调用 LLM
        response = await openai.chat(...)
        # 保存数据库
        db.add(Call(**call_data))
        # 发送通知
        await send_email(...)

# ✅ 正确: 职责分离
class CallService:
    def __init__(self, llm: LLMAdapter, repo: CallRepository, notifier: Notifier):
        self.llm = llm
        self.repo = repo
        self.notifier = notifier
    
    async def process_call(self, call_data: CallCreate) -> Call:
        response = await self.llm.generate_response(call_data.prompt)
        call = await self.repo.create(call_data)
        await self.notifier.notify(call)
        return call
```

### O - 开闭原则 (Open/Closed)
- 对扩展开放,对修改关闭
- 使用 Adapter 模式添加新提供商,而非修改现有代码

### L - 里氏替换原则 (Liskov Substitution)
- 子类可以替换父类
- 所有 Adapter 实现必须可互换

### I - 接口隔离原则 (Interface Segregation)
- 不强迫实现不需要的方法
- 使用小而专注的接口

### D - 依赖倒置原则 (Dependency Inversion)
- 依赖抽象,不依赖具体实现
- Service 依赖 `LLMAdapter` 接口,而非 `OpenAIAdapter` 类

---

## 异步编程模式

### 1. 严格异步
**所有 I/O 操作必须异步**:
```python
# ❌ 错误: 阻塞 I/O
import requests
response = requests.get(url)

# ✅ 正确: 异步 I/O
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### 2. 并发执行
**使用 `asyncio.gather` 并行化**:
```python
# ✅ 并行执行多个任务
results = await asyncio.gather(
    fetch_user(user_id),
    fetch_calls(user_id),
    fetch_appointments(user_id)
)
```

### 3. 队列模式
**生产者-消费者解耦**:
```python
audio_queue = asyncio.Queue()

async def audio_receiver():
    while True:
        chunk = await websocket.receive_bytes()
        await audio_queue.put(chunk)

async def audio_processor():
    while True:
        chunk = await audio_queue.get()
        await process_audio(chunk)
```

---

## 参考文档

- 详细架构图: [docs/ARCHITECTURE.md](file:///Users/zeng/Desktop/LLM-VoiceAgent/docs/ARCHITECTURE.md)
- 后端代码结构: `backend/app/`
- 前端组件结构: `frontend/src/components/`
