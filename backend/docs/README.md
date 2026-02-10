# 后端文档

## 📚 文档列表

### 架构设计
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 后端架构设计
  - 核心设计理念
  - 分层架构说明
  - 数据流向
  - 最终形态展望

### 配置相关
- [CONFIG.md](./CONFIG.md) - 环境配置使用说明
  - 配置文件说明
  - 使用方法
  - 配置项详解

### 数据库相关
- [DATABASE.md](./DATABASE.md) - 数据库快速启动指南
  - Docker启动
  - 数据库连接
  - 常用命令

### API开发
- [API_GUIDE.md](./API_GUIDE.md) - API开发指南
  - RESTful规范
  - 统一响应格式
  - 认证授权

### 开发规范
- [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) - 后端开发规范
  - 代码规范
  - 分层架构
  - 命名规范
  - 开发工作流

### 系统设计
- [api/appointment_system_design.md](./api/appointment_system_design.md) - 预约管理系统设计
- [api/call_system_design.md](./api/call_system_design.md) - 通话管理系统设计

---

## 🚀 快速开始

1. **配置环境变量**
   ```bash
   # 本地开发
   cp .env.local .env
   ```

2. **启动数据库**
   ```bash
   cd ..
   docker compose up -d
   ```

3. **运行后端**
   ```bash
   poetry install
   poetry run uvicorn app.main:app --reload
   ```

---

## 📖 更多文档

- 项目根目录的 [README.md](../../README.md)
- 前端文档: [frontend/docs/](../../frontend/docs/)
