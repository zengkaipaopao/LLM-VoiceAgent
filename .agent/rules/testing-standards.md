---
trigger: always_on
---

# 测试标准和覆盖率要求

## 测试原则

### 测试金字塔
```
       /\
      /  \  E2E Tests (少量)
     /----\
    / Unit \ Integration Tests (适量)
   /--------\
  /   Unit   \ Unit Tests (大量)
 /------------\
```

- **70% 单元测试**: 快速、隔离、易维护
- **20% 集成测试**: 验证组件协作
- **10% E2E 测试**: 关键用户流程

### 覆盖率要求
- **新功能**: 单元测试覆盖率 ≥ 80%
- **关键路径**: 必须有集成测试 (例: 通话流程、信息提取)
- **Bug 修复**: 必须先写失败的测试,再修复

---

## 后端测试 (Python + pytest)

### 文件命名
- 测试文件: `test_*.py` 或 `*_test.py`
- 测试类: `Test*` (例: `TestCallRepository`)
- 测试函数: `test_*` (例: `test_create_call_success`)

### 单元测试

**测试 Repository**:
```python
import pytest
from uuid import uuid4
from app.repositories.calls import CallRepository
from app.schemas.calls import CallCreate

@pytest.fixture
def call_repo(db_session):
    """提供 CallRepository 实例"""
    return CallRepository(db_session)

@pytest.fixture
def sample_call_data():
    """提供测试数据"""
    return CallCreate(
        caller_number="+8613800138000",
        callee_number="+8613900139000",
        status="active"
    )

class TestCallRepository:
    async def test_create_call_success(self, call_repo, sample_call_data):
        """测试成功创建通话记录"""
        # Arrange (准备)
        # (已通过 fixtures 完成)
        
        # Act (执行)
        call = await call_repo.create(sample_call_data)
        
        # Assert (断言)
        assert call.id is not None
        assert call.caller_number == sample_call_data.caller_number
        assert call.status == "active"
    
    async def test_get_by_id_not_found(self, call_repo):
        """测试查询不存在的记录"""
        result = await call_repo.get_by_id(uuid4())
        assert result is None
```

**测试 Service (使用 Mock)**:
```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.services.call_flow import CallFlowService

@pytest.fixture
def mock_llm_adapter():
    """Mock LLM Adapter"""
    adapter = AsyncMock()
    adapter.generate_response.return_value = "Hello, how can I help?"
    return adapter

@pytest.fixture
def mock_call_repo():
    """Mock Call Repository"""
    repo = AsyncMock()
    repo.create.return_value = MagicMock(id=uuid4(), status="active")
    return repo

class TestCallFlowService:
    async def test_start_call_success(self, mock_llm_adapter, mock_call_repo):
        """测试启动通话流程"""
        # Arrange
        service = CallFlowService(
            llm_adapter=mock_llm_adapter,
            call_repo=mock_call_repo
        )
        
        # Act
        result = await service.start_call("+8613800138000")
        
        # Assert
        assert result.status == "active"
        mock_call_repo.create.assert_called_once()
        mock_llm_adapter.generate_response.assert_called_once()
```

### 集成测试

**测试 API 端点**:
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.integration
class TestCallAPI:
    async def test_create_call_endpoint(self, async_client: AsyncClient):
        """测试创建通话 API"""
        # Arrange
        payload = {
            "caller_number": "+8613800138000",
            "callee_number": "+8613900139000"
        }
        
        # Act
        response = await async_client.post("/api/v1/calls", json=payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]
```

### Fixtures 组织

**conftest.py**:
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from httpx import AsyncClient
from app.main import app
from app.core.config import settings

@pytest.fixture(scope="session")
async def db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """提供数据库会话"""
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def async_client():
    """提供 HTTP 客户端"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行并显示覆盖率
poetry run pytest --cov=app --cov-report=term-missing

# 只运行单元测试
poetry run pytest -m "not integration"

# 只运行集成测试
poetry run pytest -m integration

# 并行运行 (需要 pytest-xdist)
poetry run pytest -n auto
```

---

## 前端测试 (React + Vitest + Testing Library)

### 文件命名
- 测试文件: `*.test.ts` 或 `*.test.tsx`
- 放置位置: 与被测试文件同目录或 `__tests__/` 目录

### 组件测试

**测试 Presentational 组件**:
```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CallCard } from './CallCard';

describe('CallCard', () => {
  const mockCall = {
    id: '123',
    callerNumber: '+8613800138000',
    status: 'completed' as const,
    startTime: new Date('2026-02-13T10:00:00Z')
  };

  it('renders call information correctly', () => {
    // Arrange & Act
    render(<CallCard call={mockCall} onSelect={() => {}} />);
    
    // Assert
    expect(screen.getByText('+8613800138000')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', async () => {
    // Arrange
    const handleSelect = vi.fn();
    const { user } = render(<CallCard call={mockCall} onSelect={handleSelect} />);
    
    // Act
    await user.click(screen.getByRole('button'));
    
    // Assert
    expect(handleSelect).toHaveBeenCalledTimes(1);
  });
});
```

**测试 Custom Hook**:
```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useCallData } from './useCallData';

describe('useCallData', () => {
  it('fetches call data successfully', async () => {
    // Arrange
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [{ id: '1', status: 'active' }] })
    });
    
    // Act
    const { result } = renderHook(() => useCallData());
    
    // Assert
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.calls).toHaveLength(1);
  });
});
```

### 集成测试

**测试页面交互**:
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CallsPage } from './CallsPage';

describe('CallsPage Integration', () => {
  it('displays calls and allows filtering', async () => {
    // Arrange
    const queryClient = new QueryClient();
    const { user } = render(
      <QueryClientProvider client={queryClient}>
        <CallsPage />
      </QueryClientProvider>
    );
    
    // Act - 等待数据加载
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    });
    
    // Act - 应用过滤器
    await user.click(screen.getByLabelText('Status Filter'));
    await user.click(screen.getByText('Completed'));
    
    // Assert
    const rows = screen.getAllByRole('row');
    expect(rows.length).toBeGreaterThan(0);
  });
});
```

### 运行测试

```bash
# 运行所有测试
npm run test

# 监听模式
npm run test:watch

# 覆盖率报告
npm run test:coverage

# UI 模式 (Vitest UI)
npm run test:ui
```

---

## 测试最佳实践

### AAA 模式
所有测试遵循 **Arrange-Act-Assert** 结构:
```python
async def test_example():
    # Arrange: 准备测试数据和依赖
    user = User(name="Test")
    
    # Act: 执行被测试的操作
    result = await service.process(user)
    
    # Assert: 验证结果
    assert result.success is True
```

### 测试命名
使用描述性名称,说明测试场景:
```python
# ✅ 好的命名
def test_create_call_with_invalid_phone_raises_validation_error():
    pass

# ❌ 不好的命名
def test_call_1():
    pass
```

### 隔离性
- 每个测试独立运行,不依赖其他测试
- 使用 fixtures 或 setup/teardown 清理状态
- 避免共享可变状态

### Mock 原则
- **Mock 外部依赖**: 数据库、API、文件系统
- **不 Mock 被测试对象**: 只 Mock 其依赖
- **验证交互**: 使用 `assert_called_with` 验证 Mock 调用

### 边界测试
测试边界条件:
- 空输入、null 值
- 最大/最小值
- 异常情况

---

## CI/CD 集成

### GitHub Actions 示例
```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Backend Tests
        run: |
          cd backend
          poetry install
          poetry run pytest --cov=app --cov-report=xml
      - name: Upload Coverage
        uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Frontend Tests
        run: |
          cd frontend
          npm ci
          npm run test:coverage
```

### 质量门禁
- **覆盖率阈值**: 新代码覆盖率 < 80% 时 CI 失败
- **测试通过**: 所有测试必须通过才能合并
- **性能测试**: 关键 API 响应时间 < 200ms
