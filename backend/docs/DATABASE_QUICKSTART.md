# 数据库启动成功! 🎉

## ✅ 已启动的服务

### PostgreSQL
- **容器名**: llm-voice-agent-db
- **端口**: 5432
- **数据库**: llm_voice_agent
- **用户名**: dev_user
- **密码**: dev_password

### Redis
- **容器名**: llm-voice-agent-redis
- **端口**: 6379

---

## 📊 数据库信息

### 连接信息
```bash
# 连接URL
postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent

# 或者分开配置
Host: localhost
Port: 5432
Database: llm_voice_agent
Username: dev_user
Password: dev_password
```

### 已创建的表
根据`init.sql`,数据库已自动创建以下表:
- ✅ `calls` - 通话记录
- ✅ `prompts` - Prompt模板
- ✅ `appointments` - 预约记录
- ✅ `agents` - Agent配置
- ✅ `models` - 支持的LLM模型

---

## 🔧 常用命令

### 查看容器状态
```bash
docker compose ps
```

### 连接数据库
```bash
# 方式1: 使用docker exec
docker exec -it llm-voice-agent-db psql -U dev_user -d llm_voice_agent

# 方式2: 使用本地psql(如果已安装)
psql -h localhost -U dev_user -d llm_voice_agent
```

### 查看表
```sql
-- 列出所有表
\dt

-- 查看表结构
\d calls
\d prompts
\d appointments
```

### 查看数据
```sql
-- 查看Prompt数据
SELECT * FROM prompts;

-- 查看模型数据
SELECT * FROM models;
```

### 停止数据库
```bash
docker compose stop
```

### 重启数据库
```bash
docker compose restart
```

### 查看日志
```bash
# PostgreSQL日志
docker compose logs postgres

# 实时查看
docker compose logs -f postgres
```

---

## 📝 下一步

### 1. 验证连接
```bash
# 测试连接
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "SELECT version();"
```

### 2. 查看初始数据
```bash
# 查看Prompt
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "SELECT * FROM prompts;"

# 查看模型
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "SELECT * FROM models;"
```

### 3. 配置后端连接
确保`.env.local`中的数据库URL正确:
```bash
DATABASE_URL=postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent
```

### 4. 测试后端连接
```bash
# 启动后端
cd backend
poetry run uvicorn app.main:app --reload
```

---

## 🎯 快速测试

```bash
# 1. 查看所有表
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "\dt"

# 2. 查看Prompt数据
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "SELECT id, name, model_id FROM prompts;"

# 3. 查看模型数据
docker exec llm-voice-agent-db psql -U dev_user -d llm_voice_agent -c "SELECT id, name, provider FROM models;"
```

---

## 🔐 安全提示

- ✅ 这是开发环境,使用简单密码
- ✅ 生产环境请使用强密码
- ✅ 数据存储在Docker卷中,删除容器不会丢失数据

---

数据库已准备就绪,可以开始开发了! 🚀
