# 后端架构设计文档

最后更新: 2026-04-30

## 1. 当前定位

本后端已经不是早期 simulation-only 骨架。当前系统同时承载：

- 浏览器直连 Gemini Live / 文本测试链路。
- Twilio 电话网关链路，包括官方 Conversational Agents、Media Streams 自建桥接、传统 Gather 模式。
- 预约创建、变更、取消、目标匹配、确定性复唱和落库。
- 测试台会话、trace 诊断、离线音频实验和人工音频注入。
- Prompt 模板、模型、音色、Twilio 入站号码配置。

核心架构仍采用 `API -> Service -> Repository -> Model` 分层，但 `services/` 内部已经按业务域拆分，避免一个服务类承担所有职责。

## 2. 分层原则

### API 层

目录：`app/api/`

职责：

- 接收 HTTP/WebSocket 参数。
- 调用鉴权、验签和 FastAPI dependency。
- 将 service 异常映射为 HTTP 响应。
- 返回 Pydantic response 或 TwiML/XML。

API 层不应该包含：

- 预约匹配规则。
- LLM runtime 解析。
- 长 WebSocket 音频桥接循环。
- 数据库更新细节。

### Service 层

目录：`app/services/`

职责：

- 业务编排。
- 预约域状态机。
- Gemini/Twilio runtime 适配。
- Prompt runtime 解析。
- 测试台 trace、audio lab、finalize/extraction 编排。

### Repository 层

目录：`app/repositories/`

职责：

- SQLAlchemy 查询。
- 分页、候选查询、按 ID 查询。
- 不写业务判断。

### Model / Schema 层

目录：

- `app/models/`: SQLAlchemy ORM。
- `app/schemas/`: Pydantic API 契约。

## 3. 当前目录结构

```text
backend/app/
├── api/
│   ├── routes.py                 # canonical router 入口
│   └── v1/
│       ├── router.py             # 兼容入口，re-export app.api.routes.api_router
│       └── endpoints/            # HTTP/WebSocket 边界
├── core/                         # 配置、数据库、日志、模型默认值
├── models/                       # SQLAlchemy ORM
├── repositories/                 # 数据访问
├── schemas/                      # Pydantic request/response
├── services/
│   ├── appointments/             # 预约业务域
│   ├── conversation/             # 文本对话编排
│   ├── extraction/               # 通话完成后的抽取编排
│   ├── live_gateway/             # 浏览器直连 Gemini Live
│   ├── test_lab/                 # 测试台 operation turn
│   ├── twilio/                   # Twilio 电话网关、Media Stream、trace
│   ├── chat_service.py           # 薄 facade，保留外部调用入口
│   ├── dashboard_service.py      # Dashboard 聚合查询
│   ├── prompt_service.py         # Prompt 模板管理
│   └── test_session_service.py   # 测试会话生命周期
└── utils/
```

## 4. 主要业务域

### 4.1 预约域

目录：`app/services/appointments/`

关键模块：

- `parsers.py`: 日文/语音转写文本解析、身份 hint、时间/数量/地址解析。
- `presenter.py`: 预约复唱文案。
- `operation_matcher.py`: 变更/取消目标预约匹配。
- `operation_flow.py`: 多轮状态机。
- `operation_executor.py`: 确认后的更新/取消和操作事件创建。
- `extraction_applier.py`: LLM 抽取结果落库和变更/取消兜底执行。

原则：

- 改预约匹配逻辑不要进 `ChatService`。
- 改取消/变更确认文案优先看 `presenter.py` 和 operation flow。
- 数据库执行必须走 executor/applier，不让 Gemini 直接决定落库。

### 4.2 对话域

目录：`app/services/conversation/`

关键模块：

- `chat_orchestrator.py`: 普通文字聊天、SSE stream、quota notice、助手输出清洗。

`ChatService` 现在只是 facade，负责把 API 旧入口连接到新的领域服务，不再承载解析、匹配、复唱等业务细节。

### 4.3 测试台域

关键模块：

- `test_session_service.py`: 测试会话 start/append/finalize。
- `test_lab/operation_turn_service.py`: 测试页面 operation turn，只推进预约变更/取消状态机，不走普通 LLM fallback。
- `twilio/trace_service.py`: trace、diagnostics、audio lab、手动音频注入。

### 4.4 浏览器直连 Gemini Live

目录：`app/services/live_gateway/`

关键模块：

- `browser_realtime.py`: Live config、modalities、音频 base64 编解码。
- `browser_websocket_bridge.py`: 浏览器 WebSocket 与 Gemini Live 的双向桥接。

API endpoint：`app/api/v1/endpoints/realtime.py`。

### 4.5 Twilio 电话网关

目录：`app/services/twilio/`

关键模块：

- `incoming_service.py`: TwiML app、入站语音、Gather 回合的 TwiML 决策。
- `media_stream_websocket_service.py`: Media Streams WebSocket bootstrap、runtime 解析、bridge context 构建。
- `media_stream_bridge_service.py`: Twilio μ-law/8k 与 Gemini Live PCM 的实时桥接。
- `audio_codec.py`: μ-law/PCM 转码与帧处理。
- `management_service.py`: Token、音色列表、下一通入站 override。
- `status_service.py`: Twilio status callback、trace 写入、finalize。
- `trace_service.py`: trace 查询、诊断、audio lab、手动音频注入。

API endpoint 已基本变薄，主要只处理验签、参数和 response。

## 5. 关键链路

### 5.1 浏览器直连文字/语音测试

```text
frontend test lab
-> /api/v1/chat or /api/v1/live/ws
-> ChatService / live_gateway service
-> Gemini / Gemini Live
-> TestSessionService finalize
-> AppointmentExtractionApplicationService
-> AppointmentExtractionApplier
-> AppointmentRepository
```

### 5.2 Twilio Media Streams 自建桥接

```text
Twilio webhook
-> /api/v1/twilio/voice/incoming
-> TwilioIncomingService builds <Connect><Stream>
-> /api/v1/twilio/voice/stream WebSocket
-> TwilioMediaStreamWebSocketService
-> run_twilio_media_stream_bridge()
-> Gemini Live
-> trace / debug wav / final extraction
```

### 5.3 官方 Conversational Agents / CX Agent Studio 对照链路

```text
Twilio incoming webhook
-> official_conversational_agents route
-> Twilio official stream connector parameters
-> Google Conversational Agents / CX Agent Studio
-> status callback / finalize
```

### 5.4 预约取消/变更

```text
user utterance
-> ConversationOrchestrator or TestSessionOperationTurnService
-> AppointmentOperationFlowService
-> AppointmentOperationMatcher
-> AppointmentBriefPresenter
-> final confirmation
-> AppointmentOperationExecutor
-> appointment original record status + operation event
```

## 6. Prompt 与确定性业务逻辑边界

Prompt 管理页面控制的是模型自然语言行为，包括：

- system prompt
- extraction prompt/schema
- LLM provider/model
- Gemini Live voice
- Twilio inbound number/default routing metadata

Prompt 不直接控制：

- 数据库更新。
- 取消/变更目标匹配。
- 最终操作事件创建。
- 所有确定性复唱文案。

这些由 appointments 域服务控制。这样做是为了避免模型幻觉直接影响数据库状态。

## 7. Router 入口

当前 canonical router 是：

```text
app/api/routes.py
```

兼容入口：

```text
app/api/v1/router.py
```

`app/api/v1/router.py` 只 re-export canonical router，避免历史半套路由再次分叉。

## 8. 维护规则

- 新 HTTP/WebSocket endpoint 先写薄 API，再把业务逻辑放入 service。
- 新预约业务逻辑放入 `services/appointments/`。
- 新 Twilio 运行时逻辑放入 `services/twilio/`。
- 新 Gemini Live 浏览器直连逻辑放入 `services/live_gateway/`。
- `ChatService` 只作为 facade，不再添加解析/匹配/落库 helper。
- 对关键状态机和 trace 诊断必须补 service 级单元测试。

## 9. 回归要求

架构重构后至少运行：

```bash
cd backend
PYTHONPATH=. poetry run pytest
PYTHONPATH=. poetry run ruff check <touched-files> --select I001,F401,F821,E999
```

前端相关联动需要运行：

```bash
cd frontend
npm run build
```

如果本机 Homebrew Node 因 ICU 动态库失败，可以使用 Codex bundled Node：

```bash
cd frontend
PATH=/Users/zeng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build
```

## 10. 延伸文档

- `backend/docs/VOICE_GATEWAYS.md`: 三条语音链路、边界和排障顺序。
- `backend/docs/MEDIA_STREAM_TRACE_FIELDS.md`: 自建 Media Streams trace 事件字段和排障判断。
- `backend/docs/APPOINTMENT_OPERATION_FLOW.md`: 预约变更/取消状态机、复唱文案和落库规则。
- `backend/docs/BUSINESS_TEMPLATE_DESIGN.md`: 确定性业务复唱模板的后续配置化方案。
- `backend/docs/SERVICE_LAYER_GUIDE.md`: 新 service 放置规则和常见开发场景。
