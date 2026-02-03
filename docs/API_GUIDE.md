# API开发指南

**版本**: 1.0

---

## API设计原则

### RESTful规范

```
GET    /api/v1/calls              # 获取列表
POST   /api/v1/calls              # 创建资源
GET    /api/v1/calls/{id}         # 获取单个
PUT    /api/v1/calls/{id}         # 更新
DELETE /api/v1/calls/{id}         # 删除
```

### HTTP状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | OK | 成功获取/更新 |
| 201 | Created | 成功创建 |
| 400 | Bad Request | 参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 不存在 |
| 500 | Server Error | 服务器错误 |

### 统一响应格式

```json
{
  "success": true,
  "data": {...},
  "meta": {
    "timestamp": "2026-02-03T10:00:00Z"
  }
}
```

---

## API端点

### 通话管理

```http
POST /api/v1/calls
{
  "caller_number": "+8613800138000",
  "callee_number": "+8613900139000",
  "prompt_id": "uuid"
}
```

```http
GET /api/v1/calls?skip=0&limit=20&status=completed
```

### 预约管理

```http
POST /api/v1/appointments
{
  "customer_name": "张三",
  "phone": "+8613800138000",
  "appointment_time": "2026-02-05T14:00:00Z"
}
```

---

## 认证

```python
from fastapi import Security
from fastapi.security import APIKeyHeader

api_key = APIKeyHeader(name="X-API-Key")

async def verify_key(key: str = Security(api_key)):
    if key not in valid_keys:
        raise HTTPException(403)
```

---

## 错误处理

```python
@app.post("/calls")
async def create_call(call: CallCreate):
    try:
        return await service.create_call(call)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
```

---

## 测试

```python
@pytest.mark.asyncio
async def test_create_call():
    async with AsyncClient(app=app) as client:
        response = await client.post("/api/v1/calls", json={...})
        assert response.status_code == 201
```

---

## 文档

FastAPI自动生成:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
