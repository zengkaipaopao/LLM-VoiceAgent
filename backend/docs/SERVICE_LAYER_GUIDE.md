# Service 层开发指南

最后更新: 2026-04-30

## 1. 当前状态

Service 层当前服务真实语音、文本测试、预约操作和诊断链路。当前后端已接入：

- Twilio Voice SDK / Webhook / Media Streams。
- Gemini Live / Gemini 文字模型。
- 官方 Conversational Agents / CX Agent Studio 对照链路。
- 测试台 trace、audio lab、会话 finalize 与预约抽取。
- 预约创建、变更、取消、目标匹配和确定性操作事件。

新的开发原则是：API 层保持薄，业务逻辑必须进入对应 service/domain 模块。

## 2. Service 分区

### 2.1 `services/appointments/`

预约业务域。

使用场景：

- 解析用户说出的日期、地址、数量、公司名、姓名。
- 生成预约复唱文案。
- 匹配取消/变更的目标预约。
- 执行取消/变更并创建操作事件。
- 将 LLM 抽取结果落库。

主要类：

- `JapaneseAppointmentParser`
- `AppointmentBriefPresenter`
- `AppointmentOperationMatcher`
- `AppointmentOperationFlowService`
- `AppointmentOperationExecutor`
- `AppointmentExtractionApplier`

不要把这些逻辑加回 `ChatService`。

### 2.2 `services/conversation/`

对话编排域。

主要类：

- `ConversationOrchestrator`

职责：

- 普通聊天 turn。
- SSE streaming。
- quota notice。
- assistant 输出清洗。
- 冗余开场白去除。
- transcript message normalization。

### 2.3 `services/extraction/`

完成通话后的抽取编排。

主要类：

- `AppointmentExtractionApplicationService`

职责：

- 判断是否已经抽取过。
- 跳过已经执行过的变更/取消。
- 调用 LLM extraction。
- 委托 `AppointmentExtractionApplier` 落库。

### 2.4 `services/test_lab/`

测试页面专用业务。

主要类：

- `TestSessionOperationTurnService`

职责：

- 测试页面中的变更/取消 operation turn。
- 只推进确定性状态机，不走普通 LLM fallback。
- 保持测试台与真实会话落库路径一致。

### 2.5 `services/live_gateway/`

浏览器直连 Gemini Live。

主要类/模块：

- `browser_realtime.py`
- `browser_websocket_bridge.py`

职责：

- Live config 构建。
- modalities 解析。
- 音频 base64 编解码。
- 浏览器 WebSocket 与 Gemini Live 的双向桥接。

### 2.6 `services/twilio/`

Twilio 电话网关和 Media Stream 实时链路。

主要模块：

- `incoming_service.py`: TwiML app、入站语音、Gather 回合。
- `media_stream_websocket_service.py`: Media Stream WebSocket bootstrap 与 runtime 构建。
- `media_stream_bridge_service.py`: Twilio 音频与 Gemini Live 双向桥。
- `audio_codec.py`: μ-law/8kHz 与 PCM16 转码。
- `management_service.py`: token、音色、入站 override。
- `status_service.py`: stream/call status callback。
- `trace_service.py`: trace、diagnostics、audio lab、手动注入。

## 3. `ChatService` 的角色

`ChatService` 现在是 facade，而不是业务逻辑集中地。

保留职责：

- `process_chat()`
- `stream_chat()`
- `extract_appointment()`
- `start_test_session()`
- `append_test_session_messages()`
- `finalize_test_session()`
- `process_test_session_operation_turn()`

禁止新增：

- 日期/地址/数量解析 helper。
- 预约复唱 helper。
- 目标预约匹配 helper。
- Twilio/Gemini runtime helper。
- 数据库更新细节。

这些必须放入对应领域 service。

## 4. API 层写法

API endpoint 应该只做四件事：

1. 接收 FastAPI 参数。
2. 调用鉴权或 Twilio webhook 验签。
3. 调用 service。
4. 把 service 结果包装成 `ResponseBase`、XML、FileResponse 或 WebSocket 输出。

示例：

```python
@router.get("/stats", response_model=ResponseBase[dict])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    return ResponseBase(success=True, data=await DashboardService(db).get_stats())
```

避免：

```python
@router.post("/some-route")
async def route(...):
    # 不要在 endpoint 中写状态机、SQL 聚合、LLM runtime 解析或长 WebSocket loop。
```

## 5. Repository 层规则

Repository 只负责数据访问：

- CRUD。
- 分页。
- 查询候选。
- join/query builder。

Repository 不做：

- 预约变更状态判断。
- Prompt 决策。
- Twilio route 决策。
- LLM response 清洗。

## 6. 典型开发场景

### 新增预约匹配规则

改：

```text
app/services/appointments/parsers.py
app/services/appointments/operation_matcher.py
```

补测试：

```text
tests/test_services/appointments/test_appointment_parser_presenter.py
tests/test_services/appointments/test_appointment_operation_matcher.py
```

### 修改取消/变更复唱内容

改：

```text
app/services/appointments/presenter.py
app/services/appointments/operation_flow.py
```

### 修改浏览器直连 Gemini Live 行为

改：

```text
app/services/live_gateway/browser_realtime.py
app/services/live_gateway/browser_websocket_bridge.py
```

### 修改 Twilio Media Stream 行为

改：

```text
app/services/twilio/media_stream_websocket_service.py
app/services/twilio/media_stream_bridge_service.py
app/services/twilio/audio_codec.py
```

### 修改 trace / audio lab

改：

```text
app/services/twilio/trace_service.py
app/services/twilio/trace_diagnostics.py
app/services/twilio/audio_lab.py
```

### 修改 Prompt 模板 CRUD

改：

```text
app/services/prompt_service.py
app/api/v1/endpoints/prompts.py
```

原则：写操作校验进入 `PromptService`，endpoint 只保留 HTTP 错误映射。

## 7. 测试要求

每次改动至少运行相关测试：

```bash
cd backend
PYTHONPATH=. poetry run pytest tests/test_services/<target-test>.py
```

跨域重构后运行：

```bash
PYTHONPATH=. poetry run pytest
```

触达文件 lint：

```bash
PYTHONPATH=. poetry run ruff check <files> --select I001,F401,F821,E999
```

涉及前端或 API response 结构时运行：

```bash
cd frontend
npm run build
```

如果本机 Homebrew Node 因 ICU 动态库失败，可以使用 Codex bundled Node：

```bash
cd frontend
PATH=/Users/zeng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build
```

## 8. 代码审查清单

提交前检查：

- endpoint 是否仍是薄入口。
- 新逻辑是否进入正确领域目录。
- 是否新增/更新 service 级测试。
- 是否保持原有 HTTP path、method、status、response schema。
- 是否避免把 Prompt 当成确定性数据库操作配置。
- 是否避免在异步 WebSocket/音频循环中阻塞 event loop。
- 是否保留 `call_sid`、`session_id` 等 trace 上下文。

## 9. 历史骨架服务

`CallService` 和 `AppointmentService` 仍保留传统列表查询和部分历史 TODO 方法。它们主要服务管理页和兼容 API，不代表实时语音主链路。

实时语音主链路应优先阅读：

```text
services/live_gateway/
services/twilio/
services/appointments/
services/conversation/
services/extraction/
```

## 10. 相关文档

- `backend/docs/ARCHITECTURE.md`: 当前后端总体结构。
- `backend/docs/VOICE_GATEWAYS.md`: 浏览器直连、官方 CX、自建 Media Streams 三条语音链路。
- `backend/docs/MEDIA_STREAM_TRACE_FIELDS.md`: 自建 Media Streams trace 事件和字段说明。
- `backend/docs/APPOINTMENT_OPERATION_FLOW.md`: 预约变更/取消状态机与确定性复唱边界。
- `backend/docs/BUSINESS_TEMPLATE_DESIGN.md`: 业务确认话术模板的配置化设计。
- `backend/docs/BACKEND_ARCHITECTURE_REVIEW.md`: 重构背景、阶段状态和后续优先级。
