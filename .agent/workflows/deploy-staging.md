---
description: 部署应用到测试环境
---

# 部署到测试环境

将应用部署到 Staging 环境进行集成测试和用户验收测试(UAT)。

## 前置检查

在部署前确保:
- [ ] 所有测试通过
- [ ] 代码已合并到 `develop` 或 `staging` 分支
- [ ] 数据库迁移已准备好
- [ ] 环境变量已配置

## 步骤

### 1. 运行测试

```bash
# 后端测试
cd backend && poetry run pytest

# 前端测试
cd frontend && npm run test
```

### 2. 构建 Docker 镜像

```bash
# 构建后端镜像
docker build -t llm-voice-agent-backend:staging ./backend

# 构建前端镜像
docker build -t llm-voice-agent-frontend:staging ./frontend
```

### 3. 推送到容器注册表

```bash
# 标记镜像
docker tag llm-voice-agent-backend:staging <registry>/llm-voice-agent-backend:staging
docker tag llm-voice-agent-frontend:staging <registry>/llm-voice-agent-frontend:staging

# 推送
docker push <registry>/llm-voice-agent-backend:staging
docker push <registry>/llm-voice-agent-frontend:staging
```

### 4. 应用数据库迁移

```bash
# SSH 到 staging 服务器
ssh staging-server

# 运行迁移
cd /app/backend
poetry run alembic upgrade head
```

### 5. 更新服务

**使用 Docker Compose**:
```bash
cd /app
docker-compose pull
docker-compose up -d
```

**使用 Kubernetes**:
```bash
kubectl set image deployment/backend backend=<registry>/llm-voice-agent-backend:staging
kubectl set image deployment/frontend frontend=<registry>/llm-voice-agent-frontend:staging
```

### 6. 验证部署

```bash
# 检查服务状态
curl https://staging.example.com/api/health

# 查看日志
docker-compose logs -f backend
# 或
kubectl logs -f deployment/backend
```

## 回滚步骤

如果部署出现问题:

```bash
# Docker Compose
docker-compose down
git checkout <previous-commit>
docker-compose up -d

# Kubernetes
kubectl rollout undo deployment/backend
kubectl rollout undo deployment/frontend
```

## 部署后检查

- [ ] 健康检查端点返回 200
- [ ] 前端可以访问
- [ ] 关键功能正常(创建通话、查看记录等)
- [ ] 数据库连接正常
- [ ] 外部服务集成正常(LLM、通信服务)
