# 运维与交接说明书

最后更新: 2026-05-25

## 1. 本地环境准备

### 1.1 基础依赖

| 组件 | 要求 |
| --- | --- |
| Python | 3.11+ |
| Node.js | 20.x |
| Docker | 支持 Docker Compose |
| PostgreSQL | 本地通过 compose 启动 |
| Redis | 本地通过 compose 启动 |
| Poetry | 后端依赖管理 |

### 1.2 启动数据库

在项目根目录执行：

```bash
docker compose up -d
```

验证：

```bash
docker exec -it llm-voice-agent-db psql -U dev_user -d llm_voice_agent
```

### 1.3 后端启动

```bash
cd backend
cp .env.example .env
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

访问：

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

### 1.4 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:5173`

## 2. 必要配置

### 2.1 后端 `.env`

最小开发配置：

```bash
ENVIRONMENT=local
DATABASE_URL=postgresql+asyncpg://dev_user:dev_password@localhost:5432/llm_voice_agent
REDIS_URL=redis://localhost:6379/0
GOOGLE_API_KEY=<dev-key>
DEFAULT_LLM_PROVIDER=gemini
DEFAULT_LIVE_PROVIDER=gemini
```

Twilio 电话链路配置：

```bash
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_API_KEY_SID=<api-key-sid>
TWILIO_API_KEY_SECRET=<api-key-secret>
TWILIO_TWIML_APP_SID=<twiml-app-sid>
TWILIO_PHONE_NUMBER=<number>
TWILIO_VALIDATE_WEBHOOKS=true
```

生产建议：

```bash
ENVIRONMENT=production
APP_API_KEY=<strong-secret>
CORS_ORIGINS=https://<frontend-domain>
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<project>
GOOGLE_CLOUD_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=
```

生产优先使用 Workload Identity/ADC，不建议长期依赖静态 JSON key 或 API key。

## 3. 数据库迁移

唯一真相源：Alembic。

常用命令：

```bash
cd backend
poetry run alembic current
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "describe change"
```

交接注意：

- 不要直接手改生产表结构。
- 新字段需要同步 ORM model、Pydantic schema、API mapper、前端 DTO。
- 迁移前备份数据库。

## 4. 测试命令

后端：

```bash
cd backend
poetry run pytest
```

前端：

```bash
cd frontend
npm run test
npm run build
npm run i18n:check
```

建议在交接验收时至少运行：

```bash
cd backend && poetry run pytest
cd frontend && npm run build
```

## 5. Twilio 本地联调

当前 Twilio 联调的首要目标是稳定 **自建 Media Streams + Gemini Live** 主链路。官方 Conversational Agents/CX Agent Studio 只作为对照组：它能帮助确认 Twilio 电话环境和上游模型能力，但不能替代本系统的本地 PromptTemplate 动态切换和业务落库主路径。

### 5.1 暴露本地后端

使用 ngrok/cloudflared 等工具将本地 `8000` 暴露为 HTTPS。

Twilio Voice URL 示例：

```text
https://<public-domain>/api/v1/twilio/voice/incoming?mode=agent&voice_engine=gemini
```

### 5.2 验证步骤

1. 先在前端测试台跑浏览器直连 Gemini Live。
2. 确认 Prompt、模型、音色可用。
3. 配置 Twilio Voice URL。
4. 拨打 Twilio 号码。
5. 打开 trace 页面或调用 trace API，确认 start/media/response/stop 事件存在。
6. 检查 debug wav 能否听清 inbound 音频。

### 5.3 常见问题

| 现象 | 排查方向 |
| --- | --- |
| Twilio 没有进入后端 | Voice URL、HTTPS、ngrok、Twilio 控制台错误 |
| WebSocket 建立后无识别 | inbound media 是否持续、μ-law 解码、debug wav |
| 只回复第一轮/第二轮后卡死 | 第二轮 inbound media 是否持续到达、Gemini Live session 是否仍 open、是否误发 audio_end、activity detection 是否混用、outbound queue 是否阻塞 receive loop、interrupted/clear 是否误触发 |
| AI 说话时用户打断无效 | interrupted 事件、outbound queue flush、Twilio clear |
| 生产 webhook 403 | Twilio 签名、反向代理转发 header/URL 是否改变 |

## 6. 发布检查清单

### 6.1 后端

- `ENVIRONMENT` 非 local。
- CORS origins 明确。
- `APP_API_KEY` 已设置。
- `TWILIO_VALIDATE_WEBHOOKS=true`。
- Alembic 已升级到 head。
- 日志中包含 request_id/call_sid/session_id。
- 关闭或限制 debug wav 的长期保存策略。

### 6.2 前端

- `npm run build` 通过。
- API base URL 指向目标后端。
- i18n key 检查通过。
- 关键页面无空白和控制台错误。

### 6.3 外部服务

- Twilio 号码、TwiML App、Voice URL、Status Callback 配置正确。
- Google/Vertex AI 项目、IAM、配额已确认。
- 数据库备份与恢复策略明确。

## 7. 运行监控建议

第一阶段至少观测：

- HTTP 5xx rate。
- WebSocket close code 分布。
- Gemini Live session 创建失败率。
- Twilio Media Streams start/stop 数。
- inbound/outbound audio chunk 计数。
- interrupted/clear 次数。
- 通话后 finalize 成功率。
- 预约抽取成功率和人工修正率。

## 8. 交接给同事的最小任务包

建议接手同事按以下顺序熟悉：

1. 跑通本地环境。
2. 阅读 `docs/handover/README.md` 和需求/设计文档。
3. 在前端创建或编辑一个 PromptTemplate。
4. 使用文本测试台完成一次预约抽取。
5. 使用浏览器直连语音完成一次多轮对话。
6. 查看数据库中的 calls/appointments/prompt_templates。
7. 阅读 Twilio trace 文档并完成一次电话联调。
8. 选择一个低风险 TODO 修复，走完整测试和提交流程。
