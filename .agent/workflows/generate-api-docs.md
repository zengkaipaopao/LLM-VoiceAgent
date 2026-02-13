---
description: 生成并导出 OpenAPI 文档
---

# 生成 API 文档

从 FastAPI 应用生成 OpenAPI 规范文档,用于 API 文档和客户端代码生成。

## 步骤

// turbo
1. 导出 OpenAPI JSON 规范
```bash
cd backend && poetry run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
```

2. 查看生成的文档
   - 文件位置: `backend/openapi.json`
   - 在线查看: 启动服务器后访问 `http://localhost:8000/docs` (Swagger UI)
   - 或访问: `http://localhost:8000/redoc` (ReDoc)

## 使用场景

- **API 文档**: 分享给前端团队或第三方集成商
- **客户端生成**: 使用 openapi-generator 生成客户端 SDK
- **API 测试**: 导入到 Postman 或 Insomnia
- **版本控制**: 提交到 Git 追踪 API 变更

## 文档质量检查

确保所有端点包含:
- `summary`: 简短描述
- `description`: 详细说明
- `response_model`: 响应模型
- `responses`: 错误响应说明
