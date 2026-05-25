# 详细设计说明书

最后更新: 2026-05-25

## 1. 后端详细设计

### 1.1 应用入口

入口文件：`backend/app/main.py`

关键行为：

- 创建 FastAPI 应用，标题来自 `settings.app_name`。
- 注册统一异常处理器：应用异常、HTTP 异常、请求校验异常、兜底异常。
- 注册 CORS 中间件；非 local 环境要求显式 origins 且禁止 wildcard。
- 注册 request_id 中间件，输出请求开始到结束耗时并回写 `X-Request-ID`。
- 挂载 `api_router` 到 `settings.api_prefix`，默认 `/api/v1`。

### 1.2 路由装配

入口文件：`backend/app/api/routes.py`

设计要点：

- `api_router` 挂载所有路由。
- `protected_router` 通过 `Depends(require_api_key)` 保护管理类 API。
- Twilio webhook 相关路由直接挂载在 `api_router`，避免外部 webhook 被 API Key 阻断；生产安全依赖 Twilio 签名校验。
- `/health` 不加保护，用于健康检查。

### 1.3 配置模型

入口文件：`backend/app/core/config.py`

主要配置域：

| 配置域 | 代表变量 |
| --- | --- |
| 应用 | `ENVIRONMENT`, `DEBUG`, `API_PREFIX` |
| 安全 | `CORS_ORIGINS`, `APP_API_KEY`, `TWILIO_VALIDATE_WEBHOOKS` |
| 数据库 | `DATABASE_URL`, `REDIS_URL` |
| Gemini | `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI`, `DEFAULT_LLM_MODEL`, `DEFAULT_LIVE_MODEL` |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_TWIML_APP_SID`, `TWILIO_PHONE_NUMBER` |
| Media Streams | `TWILIO_MEDIA_STREAM_BRIDGE_PROFILE`, `TWILIO_GEMINI_ACTIVITY_MODE`, `TWILIO_MEDIA_STREAM_INBOUND_BATCH_MS` |
| Trace/Debug | `TWILIO_MEDIA_STREAM_DEBUG_INBOUND_WAV_ENABLED`, `TWILIO_RUNTIME_STORE_BACKEND` |

生产建议：

- Gemini 使用 Vertex AI + ADC。
- `APP_API_KEY` 开启管理 API 保护。
- `TWILIO_VALIDATE_WEBHOOKS=true`。
- 多实例部署前将 runtime store 从 memory 演进为共享后端。

## 2. 数据库详细设计

### 2.1 calls

用途：记录电话或测试会话产生的通话级数据。

关键字段：

- `id`: UUID 主键。
- `direction`: inbound/outbound 等方向。
- `counterpart`: 对端号码或用户标识。
- `caller_name`: 来电人名称。
- `started_at`, `answered_at`, `ended_at`, `duration_seconds`: 时间和时长。
- `status`: ringing/answered/completed/failed 等状态。
- `handler_type`: AI 或人工等处理类型。
- `summary`, `transcript`, `ai_confidence`: LLM 输出和质量信息。
- `sip_call_id`, `sip_from`, `sip_to`: 电话网关关联字段。
- `prompt_id`, `agent_id`: 运行时配置关联。
- `extra_data`: 扩展 JSON。

### 2.2 appointments

用途：保存从对话中抽取出来的预约业务记录。

关键字段：

- `id`: UUID 主键。
- `call_id`: 关联 calls。
- `timestamp`: 记录生成时间。
- `caller_name`, `company`: 客户信息。
- `appointment`: 预约时间。
- `category`, `amount`, `address`, `summary`, `extra_request`: 业务字段。
- `operation`: create/update/delete。
- `is_handled`: 是否已人工/业务处理。
- `raw_messages`: 原始消息。
- `prompt_id`, `type_name`, `extracted_data`: Prompt 和抽取结果。

### 2.3 prompt_templates

用途：配置不同业务场景的系统 Prompt、抽取 schema、模型和语音参数。

关键字段：

- `name`, `code`, `description`, `category`。
- `system_prompt`, `extraction_prompt`。
- `variables`, `example_conversations`, `extraction_schema`。
- `response_format`, `output_schema`。
- `llm_provider`, `llm_model`, `temperature`, `max_tokens`。
- `voice_provider`, `voice_id`, `voice_settings`。
- `is_twilio_incoming_default`, `twilio_inbound_numbers`。
- `is_active`, `version`, `created_by`。

## 3. 服务层详细设计

### 3.1 PromptRuntimeResolver

职责：

- 根据请求、Prompt code、默认配置解析运行时 Prompt。
- 输出 system prompt、LLM provider/model、voice、抽取 schema。
- 为浏览器语音、Twilio 入站、文本测试提供统一配置来源。

设计原因：避免每条入口链路单独拼接 Prompt，降低行为漂移。

### 3.2 LLM Service

主要路径：`backend/app/services/llm/`

设计：

- `base.py`: 定义 provider 抽象。
- `gemini_service.py`: Gemini 文本生成和结构化输出。
- `factory.py`: 按 provider 创建服务。
- `google_genai_client.py`: Google GenAI SDK 客户端封装。

当前主供应商为 Gemini；OpenAI Key 配置存在但不是主路径。

### 3.3 实时语音 Browser Gateway

主要路径：

- `backend/app/api/v1/endpoints/realtime.py`
- `backend/app/services/live_gateway/browser_websocket_bridge.py`
- `backend/app/services/live_gateway/browser_realtime.py`

职责：

- 接收前端 WebSocket。
- 建立 Gemini Live session。
- 透传浏览器音频、文本和控制事件。
- 转发 Gemini Live 音频、文本、turn 和错误事件。
- 会话结束后触发测试会话 finalize 和预约抽取。

并发模型建议：

- Receiver: 接收浏览器输入。
- Processor: 与 Gemini Live 双向交换事件。
- Sender: 向前端发送输出。
- 使用 `asyncio.TaskGroup` 管理生命周期，任一关键任务失败应取消同组任务并清理 session。

### 3.4 Twilio Media Streams Gateway

主要路径：

- `backend/app/api/v1/endpoints/twilio_incoming.py`
- `backend/app/api/v1/endpoints/twilio_legacy_stream.py`
- `backend/app/services/twilio/media_stream_websocket_service.py`
- `backend/app/services/twilio/media_stream_bridge_service.py`
- `backend/app/services/twilio/audio_codec.py`
- `backend/app/services/twilio/trace_service.py`

核心职责：

1. 入站 webhook 根据 `mode`、`voice_engine`、Prompt 映射生成 TwiML。
2. Media Stream WebSocket 接收 `start/media/stop` 事件。
3. 将 Twilio `audio/x-mulaw; rate=8000` 解码并升采样为 Gemini 可接受的 PCM。
4. 接收 Gemini Live 输出音频，降采样并编码为 μ-law 回传 Twilio。
5. 处理 interrupted/start_of_speech：清空 outbound 队列、发送 Twilio `clear`、取消或抑制未完成回复。
6. 持续写入 trace、media stats、debug wav。

当前 P0 问题：

- 浏览器直连 Gemini Live 已能验证模型和 Prompt 能力，但真实电话主链路仍卡在自建 Media Streams 的多轮稳定性。
- 官方 Conversational Agents/CX Agent Studio 需要在 Google 平台维护流程和参数，无法作为本地 `PromptTemplate` 动态切换的主路径。
- 自建 Media Streams 第二轮后处理/turn state 需要优先修复。排查时必须先确认第二轮 inbound media 是否持续进入后端，再确认 Gemini Live session、activity detection、outbound queue、interrupted/clear 和 receive loop 状态。

关键约束：

- 音频循环内禁止同步 DB、文件大写入、阻塞网络调用。
- 自动 activity detection 与手动 activity_start/activity_end 不能混用。
- 生产调参必须基于 trace 和 debug wav，而不是只看主观通话体验。

### 3.5 预约操作服务

主要路径：`backend/app/services/appointments/`

组件：

- `parsers.py`: 将抽取文本/JSON 转为内部结构。
- `operation_matcher.py`: 判断 create/update/delete 并匹配目标预约。
- `operation_flow.py`: 编排预约操作流程。
- `operation_executor.py`: 执行数据库变更。
- `extraction_applier.py`: 将 LLM 抽取结果应用到业务模型。
- `presenter.py`: 输出展示用格式。

设计原因：预约规则是业务核心，必须独立于语音入口，避免 Twilio、浏览器测试、文本测试出现三套落库逻辑。

## 4. 前端详细设计

### 4.1 页面结构

| 页面 | 文件 | 说明 |
| --- | --- | --- |
| Dashboard | `frontend/src/pages/Dashboard.tsx` | 统计概览和系统状态 |
| Calls | `frontend/src/pages/Calls.tsx` | 通话列表和详情 |
| Appointments | `frontend/src/pages/Appointments.tsx` | 预约列表、Prompt 筛选、处理状态 |
| Prompts | `frontend/src/pages/Prompts.tsx` | Prompt 管理 |
| Test | `frontend/src/pages/Test.tsx` | 文本/语音/Twilio 测试台 |
| Settings | `frontend/src/pages/Settings.tsx` | 系统配置展示 |

### 4.2 API 边界

主要路径：`frontend/src/api/`

设计要求：

- HTTP 客户端统一处理 base URL、错误和认证头。
- API DTO 与 UI Domain Model 分离。
- 对后端响应进行运行时校验；新增接口建议继续使用 Zod。
- snake_case 与 camelCase 转换只允许出现在 API 层或 mapper 层。

### 4.3 实时 UI

语音测试相关逻辑主要在：

- `frontend/src/hooks/useLiveWebSocketConsole.ts`
- `frontend/src/hooks/liveConsole/`
- `frontend/src/features/test-lab/voice/`

设计要求：

- 高频 WebSocket/audio 状态使用 `useRef` 保存，避免每个音频 chunk 触发 React re-render。
- UI 状态只同步必要的事件、转写、错误和会话状态。
- 音频播放、心跳、麦克风采集拆成独立 hook，便于隔离排障。

## 5. 错误处理设计

| 场景 | 处理策略 |
| --- | --- |
| 请求校验失败 | FastAPI RequestValidationError -> 统一错误响应 |
| 业务异常 | AppException -> 统一错误响应 |
| 未捕获异常 | 记录 request_id 和栈信息，返回通用错误 |
| WebSocketDisconnect | 清理 runtime/session，记录 close code |
| Gemini 配额/认证错误 | 返回可理解错误，避免前端只看到连接断开 |
| Twilio webhook 签名失败 | 拒绝请求并记录来源 |
| 用户打断 | 清空 outbound 队列、发送 clear、取消/抑制旧回复 |

## 6. 测试设计

当前仓库包含后端 API/service 测试和前端 Vitest 测试。新增功能建议按风险分层：

- 纯业务规则：单元测试。
- API schema/路由：FastAPI TestClient 测试。
- 语音转码：输入输出格式、采样率、边界数据测试。
- WebSocket 桥：mock Gemini/Twilio 的异步集成测试。
- 前端复杂 hook：Vitest + React Testing Library。
- 端到端电话：以 trace、debug wav、manual checklist 做验收证据。
