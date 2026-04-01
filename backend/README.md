# LLM Voice Agent - 后端

企业级语音AI助手后端服务

## 🚀 快速开始

### 1. 环境配置

```bash
# 本地开发
cp .env.example .env

# 填入你的API密钥
vim .env
```

### 2. 启动数据库

```bash
# 在项目根目录
cd ..
docker compose up -d

# 验证数据库
docker exec -it llm-voice-agent-db psql -U dev_user -d llm_voice_agent
```

### 3. 安装依赖

```bash
poetry install
```

### 4. 运行服务

```bash
# 开发模式
poetry run uvicorn app.main:app --reload

# 访问
# API: http://localhost:8000
# 文档: http://localhost:8000/docs
```

---

## 📁 项目结构

```
backend/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   ├── core/              # 核心配置
│   ├── models/            # SQLAlchemy模型
│   ├── repositories/      # 数据访问层
│   ├── schemas/           # Pydantic模型
│   ├── services/          # 业务逻辑层 (Simulation)
│   └── utils/             # 工具函数
│
├── tests/                 # 测试
├── docs/                  # 文档
├── alembic/               # 数据库迁移
│
├── .env                   # 当前环境变量(不提交)
├── .env.example           # 配置示例(可提交)
├── Dockerfile             # 容器构建文件
├── .dockerignore
├── .gitignore
├── pyproject.toml
└── init.sql               # 数据库初始化脚本
```

---

## 📚 文档

- [配置说明](./docs/CONFIG.md)
- [数据库指南](./docs/DATABASE.md)
- [开发规范](./docs/DEVELOPMENT_GUIDE.md)

---

## 🔧 技术栈

- **框架**: FastAPI
- **数据库**: PostgreSQL + SQLAlchemy
- **迁移工具**: Alembic
- **模拟引擎**: Custom Simulation Service

---

## 🌍 环境说明

### 本地开发
- 配置文件: 复制 `.env.example` 到 `.env`
- 数据库: Docker PostgreSQL

---

## 📝 开发流程

1. 创建功能分支
2. 编写代码(遵循开发规范)
3. 编写测试
4. 提交代码
5. 创建Pull Request

详见 [开发规范](./docs/DEVELOPMENT_GUIDE.md)

---

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api/

# 查看覆盖率
pytest --cov=app tests/
```

---

## 📦 部署

### Docker部署

```bash
# 构建镜像
docker build -t llm-voice-agent-backend .

# 运行容器
docker run -p 8000:8000 llm-voice-agent-backend
```

### AWS部署

参考 [AWS迁移指南](../docs/aws_migration_guide.md)

---

## 🔐 安全注意事项

- ✅ 永远不要提交`.env`文件
- ✅ 使用强密码
- ✅ 定期轮换API密钥
- ✅ 生产环境使用AWS Secrets Manager

---

## 📞 联系方式

如有问题,请查看文档或联系团队成员。
