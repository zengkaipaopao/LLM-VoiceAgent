# 数据库快速启动指南

## 🚀 快速开始

### 1. 启动数据库

```bash
# 在backend目录下
cd /Users/zeng/Desktop/LLM-VoiceAgent/backend

# 启动PostgreSQL和Redis
docker-compose up -d

# 查看日志
docker-compose logs -f postgres
```

### 2. 验证数据库

```bash
# 连接数据库
docker exec -it llm-voice-agent-db psql -U dev_user -d llm_voice_agent

# 查看表
\dt

# 查看Prompt数据
SELECT * FROM prompts;

# 退出
\q
```

### 3. 更新.env配置

数据库URL已经在`.env`中配置好了:
```bash
DATABASE_URL=postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent
```

---

## 📊 数据库信息

- **数据库名**: llm_voice_agent
- **用户名**: dev_user
- **密码**: dev_password
- **端口**: 5432
- **连接URL**: postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent

---

## 🗂️ 表结构

### calls - 通话记录
- id (UUID)
- direction (inbound/outbound)
- counterpart (对方号码)
- started_at (开始时间)
- duration_seconds (时长)
- status (状态)
- summary (摘要)
- transcript (转写文本)

### prompts - Prompt模板
- id (UUID)
- name (名称)
- model_id (模型ID)
- system_prompt (系统提示词)
- capabilities (JSONB - 功能配置)
- voice_config (JSONB - 语音配置)

### appointments - 预约记录
- id (UUID)
- call_id (关联通话)
- caller_name (来电者姓名)
- appointment (预约内容)
- timestamp (预约时间)

### agents - Agent配置
- id (UUID)
- name (名称)
- llm_provider (LLM提供商)
- temperature (温度参数)

### models - 支持的模型
- id (模型ID)
- name (模型名称)
- provider (提供商)

---

## 🔧 常用命令

### Docker操作

```bash
# 启动
docker-compose up -d

# 停止
docker-compose stop

# 重启
docker-compose restart

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f postgres

# 停止并删除(保留数据)
docker-compose down

# 停止并删除(包括数据)
docker-compose down -v
```

### 数据库操作

```bash
# 连接数据库
docker exec -it llm-voice-agent-db psql -U dev_user -d llm_voice_agent

# 备份数据库
docker exec llm-voice-agent-db pg_dump -U dev_user llm_voice_agent > backup.sql

# 恢复数据库
docker exec -i llm-voice-agent-db psql -U dev_user llm_voice_agent < backup.sql

# 查看所有表
\dt

# 查看表结构
\d calls

# 查看索引
\di

# 执行SQL文件
docker exec -i llm-voice-agent-db psql -U dev_user llm_voice_agent < init.sql
```

---

## 🐛 故障排查

### 端口被占用

```bash
# 查看5432端口占用
lsof -i :5432

# 杀死占用进程
kill -9 <PID>
```

### 重置数据库

```bash
# 停止并删除所有数据
docker-compose down -v

# 重新启动
docker-compose up -d
```

### 查看容器日志

```bash
# 查看PostgreSQL日志
docker-compose logs postgres

# 实时查看日志
docker-compose logs -f postgres
```

---

## 📝 下一步

1. ✅ 启动数据库: `docker-compose up -d`
2. ✅ 验证连接: 连接数据库查看表
3. ⏭️ 配置SQLAlchemy: 创建ORM模型
4. ⏭️ 创建API: 实现CRUD操作
5. ⏭️ 数据迁移: 从JSON迁移到PostgreSQL
