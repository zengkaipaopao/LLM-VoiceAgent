# 环境配置使用说明

## 📁 配置文件说明

### 1. `.env.example` - 模板文件
- **用途**: Git提交的模板,供团队参考
- **内容**: 所有配置项的示例,不包含真实密钥
- **提交**: ✅ 提交到Git

### 2. `.env.local` - 本地开发配置
- **用途**: 本地开发环境使用
- **内容**: 本地数据库、本地存储等配置
- **提交**: ❌ 不提交到Git

### 3. `.env.aws` - AWS生产配置
- **用途**: AWS云端环境配置模板
- **内容**: RDS、S3、ElastiCache等AWS服务配置
- **提交**: ❌ 不提交到Git
- **注意**: 实际使用时,密钥应从AWS Secrets Manager获取

### 4. `.env` - 当前使用的配置
- **用途**: 实际运行时使用的配置
- **内容**: 从`.env.local`或`.env.aws`复制而来
- **提交**: ❌ 不提交到Git

---

## 🚀 使用方法

### 本地开发

```bash
# 1. 复制本地配置
cp .env.local .env

# 2. 编辑.env,填入真实值
vim .env

# 3. 启动应用
uvicorn app.main:app --reload
```

### AWS部署

```bash
# 1. 复制AWS配置
cp .env.aws .env

# 2. 配置AWS Secrets Manager
aws secretsmanager create-secret \
  --name llm-voice-agent/db-password \
  --secret-string "your-db-password"

# 3. 在ECS任务定义中引用Secrets
# 见下方ECS配置示例
```

---

## 🔐 密钥管理

### 本地开发
- 密钥存储在`.env`文件中
- 文件权限设置为600: `chmod 600 .env`
- 永远不要提交到Git

### AWS生产环境
- 密钥存储在**AWS Secrets Manager**
- ECS任务从Secrets Manager自动获取
- 不在代码或配置文件中硬编码

---

## 📊 配置优先级

```
环境变量 > .env文件 > 默认值
```

示例:
```bash
# 1. 默认值(代码中)
DATABASE_URL = "postgresql://localhost/db"

# 2. .env文件覆盖
DATABASE_URL=postgresql://dev:pass@localhost/mydb

# 3. 环境变量覆盖(优先级最高)
export DATABASE_URL=postgresql://prod:pass@rds/mydb
```

---

## 🔧 配置项说明

### 数据库配置

```bash
# 完整URL格式(推荐)
DATABASE_URL=postgresql://user:password@host:port/dbname

# 或者分开配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=dev_user
DB_PASSWORD=dev_password
DB_NAME=llm_voice_agent
```

### 文件存储配置

```bash
# 本地开发
STORAGE_TYPE=local
STORAGE_PATH=./data/uploads

# AWS生产
STORAGE_TYPE=s3
S3_BUCKET_NAME=llm-voice-agent-recordings
S3_REGION=ap-northeast-1
```

### LLM配置

```bash
# API密钥
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_API_KEY=xxx

# 默认配置
DEFAULT_LLM_PROVIDER=openai  # openai | anthropic | google
DEFAULT_LLM_MODEL=gpt-4
DEFAULT_TEMPERATURE=0.7
```

---

## 🌍 环境区分

### 开发环境 (development)
```bash
ENV=development
DEBUG=True
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost/dev_db
STORAGE_TYPE=local
```

### 预发布环境 (staging)
```bash
ENV=staging
DEBUG=False
LOG_LEVEL=INFO
DATABASE_URL=postgresql://rds-staging/db
STORAGE_TYPE=s3
```

### 生产环境 (production)
```bash
ENV=production
DEBUG=False
LOG_LEVEL=WARNING
DATABASE_URL=postgresql://rds-prod/db
STORAGE_TYPE=s3
```

---

## 📝 .gitignore配置

确保以下文件不被提交:

```gitignore
# 环境变量文件
.env
.env.local
.env.aws
.env.*.local

# 但保留模板
!.env.example

# 其他敏感文件
*.key
*.pem
credentials.json
```

---

## 🔄 配置更新流程

### 添加新配置项

1. 在`.env.example`中添加示例
2. 在`.env.local`和`.env.aws`中添加实际值
3. 在`app/core/config.py`中添加配置类字段
4. 更新此文档

### 修改配置值

1. 本地开发: 直接修改`.env`
2. AWS生产: 更新Secrets Manager或环境变量
3. 重启应用使配置生效

---

## 🚨 安全注意事项

1. ✅ 永远不要提交`.env`文件到Git
2. ✅ 使用强密码和随机密钥
3. ✅ 定期轮换密钥
4. ✅ 生产环境使用Secrets Manager
5. ✅ 限制配置文件权限: `chmod 600 .env`
6. ❌ 不要在日志中打印密钥
7. ❌ 不要在错误信息中暴露配置

---

## 📚 相关文档

- [AWS Secrets Manager文档](https://docs.aws.amazon.com/secretsmanager/)
- [12-Factor App配置管理](https://12factor.net/config)
- [Pydantic Settings文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
