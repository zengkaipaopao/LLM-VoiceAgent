---
trigger: always_on
---

# API 设计规范

## RESTful 设计原则

### 1. 资源命名

**使用复数名词**:
```
✅ GET /api/v1/calls
✅ GET /api/v1/appointments
❌ GET /api/v1/call
❌ GET /api/v1/getAppointments
```

**使用层级关系**:
```
✅ GET /api/v1/calls/{call_id}/transcripts
✅ GET /api/v1/prompts/{prompt_id}/versions
❌ GET /api/v1/call-transcripts?call_id={id}
```

**使用小写和连字符**:
```
✅ /api/v1/call-recordings
❌ /api/v1/callRecordings
❌ /api/v1/call_recordings
```

### 2. HTTP 方法

**标准 CRUD 映射**:
| 操作 | HTTP 方法 | 端点示例 | 说明 |
|------|----------|---------|------|
| 创建 | POST | `POST /calls` | 创建新资源 |
| 读取列表 | GET | `GET /calls` | 获取资源列表 |
| 读取单个 | GET | `GET /calls/{id}` | 获取单个资源 |
| 更新 | PUT | `PUT /calls/{id}` | 完整更新 |
| 部分更新 | PATCH | `PATCH /calls/{id}` | 部分更新 |
| 删除 | DELETE | `DELETE /calls/{id}` | 删除资源 |

**幂等性**:
- GET, PUT, DELETE 必须幂等
- POST 不保证幂等
- 使用幂等性键处理重复请求

### 3. 查询参数

**分页**:
```
GET /api/v1/calls?page=1&page_size=20
GET /api/v1/calls?offset=0&limit=20
```

**过滤**:
```
GET /api/v1/calls?status=completed
GET /api/v1/calls?caller_number=+8613800138000
GET /api/v1/calls?start_date=2026-02-01&end_date=2026-02-13
```

**排序**:
```
GET /api/v1/calls?sort=start_time:desc
GET /api/v1/calls?sort=duration:asc,start_time:desc
```

**字段选择**:
```
GET /api/v1/calls?fields=id,caller_number,status
```

---

## 请求/响应格式

### 统一响应结构

**成功响应**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "caller_number": "+8613800138000",
    "status": "completed",
    "start_time": "2026-02-13T10:00:00Z",
    "duration_seconds": 125.5
  },
  "meta": {
    "timestamp": "2026-02-13T10:05:00Z",
    "request_id": "req_abc123"
  }
}
```

**列表响应 (带分页)**:
```json
{
  "success": true,
  "data": [
    { "id": "...", "caller_number": "..." },
    { "id": "...", "caller_number": "..." }
  ],
  "meta": {
    "timestamp": "2026-02-13T10:05:00Z",
    "request_id": "req_abc123",
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 156,
      "total_pages": 8
    }
  }
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid phone number format",
    "details": {
      "field": "caller_number",
      "constraint": "Must be in E.164 format (e.g., +8613800138000)"
    }
  },
  "meta": {
    "timestamp": "2026-02-13T10:05:00Z",
    "request_id": "req_abc123"
  }
}
```

### 错误代码规范

**标准错误代码**:
| HTTP 状态 | 错误代码 | 说明 |
|----------|---------|------|
| 400 | `VALIDATION_ERROR` | 请求参数验证失败 |
| 401 | `UNAUTHORIZED` | 未认证 |
| 403 | `FORBIDDEN` | 无权限 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` | 资源冲突 (如重复创建) |
| 422 | `UNPROCESSABLE_ENTITY` | 语义错误 |
| 429 | `RATE_LIMIT_EXCEEDED` | 超过速率限制 |
| 500 | `INTERNAL_SERVER_ERROR` | 服务器错误 |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 |

---

## Pydantic 模型设计

### 请求模型

**创建资源**:
```python
from pydantic import BaseModel, Field, validator
from datetime import datetime

class CallCreate(BaseModel):
    """创建通话请求"""
    caller_number: str = Field(
        ..., 
        description="主叫号码 (E.164 格式)",
        example="+8613800138000"
    )
    callee_number: str = Field(
        ...,
        description="被叫号码 (E.164 格式)",
        example="+8613900139000"
    )
    prompt_id: Optional[UUID] = Field(
        None,
        description="使用的 Prompt ID"
    )
    
    @validator('caller_number', 'callee_number')
    def validate_phone_number(cls, v):
        """验证电话号码格式"""
        if not v.startswith('+') or not v[1:].isdigit():
            raise ValueError('Phone number must be in E.164 format')
        if len(v) < 8 or len(v) > 16:
            raise ValueError('Phone number length must be 8-16 characters')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "caller_number": "+8613800138000",
                "callee_number": "+8613900139000",
                "prompt_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
```

**更新资源**:
```python
class CallUpdate(BaseModel):
    """更新通话请求 (所有字段可选)"""
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    transcript: Optional[str] = None
    
    class Config:
        # 允许部分更新
        extra = 'forbid'
```

### 响应模型

```python
from datetime import datetime
from uuid import UUID

class CallResponse(BaseModel):
    """通话响应"""
    id: UUID
    caller_number: str
    callee_number: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    
    class Config:
        from_attributes = True  # 允许从 ORM 模型转换
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
```

### 通用响应包装

```python
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    success: bool
    data: Optional[T] = None
    error: Optional[dict] = None
    meta: dict
    
class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    success: bool
    data: list[T]
    meta: dict  # 包含 pagination 信息
```

---

## FastAPI 端点实现

### 标准 CRUD 端点

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from app.schemas.calls import CallCreate, CallUpdate, CallResponse
from app.repositories.calls import CallRepository

router = APIRouter(prefix="/api/v1/calls", tags=["calls"])

@router.post(
    "",
    response_model=APIResponse[CallResponse],
    status_code=201,
    summary="创建通话",
    description="发起新的呼出通话或记录呼入通话"
)
async def create_call(
    call_data: CallCreate,
    repo: CallRepository = Depends(get_call_repository)
) -> APIResponse[CallResponse]:
    """创建通话记录"""
    try:
        call = await repo.create(call_data)
        return APIResponse(
            success=True,
            data=CallResponse.from_orm(call),
            meta={"timestamp": datetime.utcnow(), "request_id": generate_request_id()}
        )
    except Exception as e:
        logger.error(f"Failed to create call: {e}")
        raise HTTPException(status_code=500, detail="Failed to create call")

@router.get(
    "",
    response_model=PaginatedResponse[CallResponse],
    summary="获取通话列表",
    description="分页查询通话记录,支持过滤和排序"
)
async def list_calls(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤"),
    repo: CallRepository = Depends(get_call_repository)
) -> PaginatedResponse[CallResponse]:
    """获取通话列表"""
    offset = (page - 1) * page_size
    calls, total = await repo.list_with_count(
        offset=offset,
        limit=page_size,
        status=status
    )
    
    return PaginatedResponse(
        success=True,
        data=[CallResponse.from_orm(call) for call in calls],
        meta={
            "timestamp": datetime.utcnow(),
            "request_id": generate_request_id(),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    )

@router.get(
    "/{call_id}",
    response_model=APIResponse[CallResponse],
    summary="获取通话详情"
)
async def get_call(
    call_id: UUID,
    repo: CallRepository = Depends(get_call_repository)
) -> APIResponse[CallResponse]:
    """获取单个通话详情"""
    call = await repo.get_by_id(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return APIResponse(
        success=True,
        data=CallResponse.from_orm(call),
        meta={"timestamp": datetime.utcnow(), "request_id": generate_request_id()}
    )

@router.patch(
    "/{call_id}",
    response_model=APIResponse[CallResponse],
    summary="更新通话"
)
async def update_call(
    call_id: UUID,
    call_data: CallUpdate,
    repo: CallRepository = Depends(get_call_repository)
) -> APIResponse[CallResponse]:
    """部分更新通话记录"""
    call = await repo.update(call_id, call_data)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return APIResponse(
        success=True,
        data=CallResponse.from_orm(call),
        meta={"timestamp": datetime.utcnow(), "request_id": generate_request_id()}
    )

@router.delete(
    "/{call_id}",
    status_code=204,
    summary="删除通话"
)
async def delete_call(
    call_id: UUID,
    repo: CallRepository = Depends(get_call_repository)
):
    """删除通话记录"""
    success = await repo.delete(call_id)
    if not success:
        raise HTTPException(status_code=404, detail="Call not found")
    return None
```

---

## 版本控制

### URL 版本控制
```python
# ✅ 推荐: URL 路径版本
/api/v1/calls
/api/v2/calls

# ❌ 不推荐: Header 版本
# Accept: application/vnd.api.v1+json
```

### 向后兼容
- 新增字段不破坏兼容性
- 删除字段需要版本升级
- 修改字段类型需要版本升级

---

## 安全性

### 认证
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key not in settings.VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### 速率限制
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/calls")
@limiter.limit("100/minute")
async def list_calls():
    pass
```

### 输入验证
- 所有输入使用 Pydantic 验证
- 防止 SQL 注入 (使用 ORM)
- 防止 XSS (转义输出)
- 限制请求大小

---

## 文档

### OpenAPI 自动生成
FastAPI 自动生成 OpenAPI 文档,访问:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### 增强文档
```python
@router.post(
    "/calls",
    response_model=APIResponse[CallResponse],
    status_code=201,
    summary="创建通话",
    description="发起新的呼出通话或记录呼入通话",
    responses={
        201: {"description": "通话创建成功"},
        400: {"description": "请求参数验证失败"},
        500: {"description": "服务器内部错误"}
    }
)
async def create_call(call_data: CallCreate):
    """
    创建新的通话记录
    
    - **caller_number**: 主叫号码 (E.164 格式)
    - **callee_number**: 被叫号码 (E.164 格式)
    - **prompt_id**: 可选,使用的 Prompt 模板 ID
    """
    pass
```
