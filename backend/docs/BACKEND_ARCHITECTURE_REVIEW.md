# 后端架构审视与改善方案

最后更新: 2026-04-30

## 1. 结论

当前后端已经有基础分层结构：`api -> services -> repositories -> models/schemas`。这个方向是对的，Twilio Media Streams 相关代码也已经比早期更模块化。本轮重构已经把主要业务边界拆开，`app/services/chat_service.py` 已从上帝类收缩成 facade。

当前最需要治理的不是“重写系统”，而是把已经混在一起的职责拆回明确的领域模块，让新接手的人可以通过目录名理解系统：

- 电话/浏览器语音链路属于传输层和实时会话层。
- Gemini/LLM 调用属于模型适配层。
- 预约创建、变更、取消属于预约业务域。
- 测试页面会话属于 test lab 域。
- Prompt 模板是配置和运行时解析域，不应该承载确定性数据库操作逻辑。

## 1.1 当前落地状态

截至 2026-04-30，Phase 1-6 的主体工作已落地：

- 已新增 `app/services/appointments/parsers.py`，集中维护日文预约文本解析、ASR 空格日期解析、姓名/公司/电话/数量/地址提取、目标匹配打分辅助逻辑。
- 已新增 `app/services/appointments/presenter.py`，集中维护预约复唱文案格式化。
- 已新增 `app/services/appointments/operation_matcher.py`，集中维护预约变更/取消的目标候选查询与匹配。
- 已新增 `app/services/appointments/operation_executor.py`，集中维护确认后的预约更新/取消、操作事件创建、`operation_execution` 写回。
- 已新增 `app/services/appointments/operation_flow.py`，集中维护预约变更/取消的多状态对话流。
- 已新增 `app/services/appointments/extraction_applier.py`，集中维护 LLM 抽取结果落库、变更/取消兜底执行、目标匹配失败响应。
- 已新增 `app/services/conversation/chat_orchestrator.py`，集中维护普通文字聊天、SSE 流式聊天、quota notice、助手输出清洗、模型注入 `User:` 截断。
- 已新增 `app/services/test_lab/operation_turn_service.py`，集中维护测试台 operation turn，只推进预约变更/取消状态机，不走普通 LLM fallback。
- 已新增 `app/services/extraction/appointment_application_service.py`，集中维护完成通话后的抽取编排、重复抽取短路、已执行变更/取消短路、LLM extraction 调用与 applier 调用。
- 已新增 `app/services/live_gateway/browser_realtime.py` 与 `browser_websocket_bridge.py`，把浏览器直连 Gemini Live 的配置解析、音频编解码、WebSocket 长循环从 API endpoint 下沉到 live gateway service。
- 已新增 `app/services/twilio/trace_service.py`，集中维护 Twilio trace 查询、诊断聚合、audio lab、debug wav 路径、手动音频注入和 active stream 汇总。
- 已新增 `app/services/twilio/incoming_service.py`，集中维护 Twilio TwiML app webhook、入站语音路由、Gather 回合的 Prompt/runtime 解析与 TwiML 生成。
- 已新增 `app/services/twilio/management_service.py`，集中维护 Twilio Voice SDK token、Gemini 音色列表、下一通入站 override 准备。
- 已新增 `app/services/twilio/status_service.py`，集中维护 Twilio stream/call status callback 的 trace 写入、session 清理与通话结束 finalize。
- 已新增 `app/services/twilio/media_stream_websocket_service.py`，集中维护 Twilio Media Streams WebSocket 的 bootstrap、runtime 解析、模型/音色选择与 bridge context 构建。
- 已新增 `app/services/dashboard_service.py`，集中维护仪表盘统计 SQL、趋势生成、数据库/Redis/AI 健康检查。
- `ChatService` 已委托上述模块，原解析/复唱实现已从 `chat_service.py` 删除。
- `ChatService` 的目标匹配、执行动作、多状态对话流已通过兼容入口委托到 appointment domain 模块。
- `ChatService.extract_appointment()` 已委托 `AppointmentExtractionApplier`，不再直接处理预约创建/变更/取消兜底细节。
- `ChatService.process_chat()` 与 `stream_chat()` 已委托 `ConversationOrchestrator`，`ChatService` 开始接近 facade。
- `ChatService.process_test_session_operation_turn()` 已委托 `TestSessionOperationTurnService`。
- `ChatService.extract_appointment()` 已委托 `AppointmentExtractionApplicationService`。
- `ChatService` 中用于迁移期的旧私有 helper alias 已删除；解析、复唱、候选匹配测试已直接指向所属领域模块。
- `chat_service.py` 已从 2415 行收缩到 217 行。
- 已新增并按领域整理 `tests/test_services/appointments/`、`conversation/`、`extraction/`、`test_lab/`、`twilio/`、`live_gateway/` 等测试目录，覆盖新模块。
- 已修复 Test Lab 直连语音会话结束收口：`finalize_test_session()` 现在会复制 JSON 后写入 `finalized_at / appointment_id / extraction_status`，避免 SQLAlchemy JSON 字段未被判定 dirty。
- 已在前端直连语音页增加离开页面时的静默 finalize，避免用户从语音测试页直接切到预约管理时，会话没有统一完成抽取。

Phase 4 的核心目标已经完成：`ChatService` 已低于 300 行，并且对话、测试台 operation turn、抽取落库都已有明确领域模块。
Phase 5 的主体目标已经完成：`app/api/v1/router.py` 已改为 re-export `app.api.routes.api_router` 的兼容入口，避免旧 router 暴露过期半套路由；`realtime.py` 已从 654 行收缩到 148 行；`twilio_trace.py` 已从 322 行收缩到 207 行；`twilio_incoming.py` 已从 465 行收缩到 112 行；`twilio_management.py` 已从 132 行收缩到 75 行；`twilio_status.py` 已从 125 行收缩到 73 行；`twilio_legacy_stream.py` 已从 196 行收缩到 23 行。
`dashboard.py` 已从 240 行收缩到 19 行，统计查询和健康检查已下沉到 `DashboardService`。`chat.py` 已统一通过 `ChatService` facade 处理 test session start/append/finalize，并清理了重复异常分支。
`prompts.py` 的创建、更新、删除细节已回收到 `PromptService`，endpoint 只保留参数接收、HTTP 错误映射和响应包装。
Phase 6 已完成文档基线更新：`ARCHITECTURE.md` 与 `SERVICE_LAYER_GUIDE.md` 已从 simulation-era 文档改为当前 Twilio/Gemini/Test Lab/预约域结构文档，并补充本机 bundled Node 构建说明；同时新增 `VOICE_GATEWAYS.md`、`MEDIA_STREAM_TRACE_FIELDS.md`、`APPOINTMENT_OPERATION_FLOW.md` 和 `BUSINESS_TEMPLATE_DESIGN.md` 四个专项文档。

当前回归基线：

- `PYTHONPATH=. poetry run pytest`: 210 passed, 4 warnings。
- touched Python 文件 `ruff check --select I001,F401,F821,E999`: passed。
- `git diff --check`: passed。
- `PATH=/Users/zeng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build`: passed。
- 关键 HTTP/WebSocket 路由断言：14 个 HTTP route + 1 个 WebSocket route passed。

## 2. 当前目录状态

当前主目录：

```text
backend/app/
├── api/                 # FastAPI 路由与依赖
├── core/                # 配置、数据库、日志、模型默认值
├── models/              # SQLAlchemy ORM
├── repositories/        # 数据访问
├── schemas/             # Pydantic API 契约
├── services/            # 业务服务、LLM、Twilio、测试会话、抽取逻辑
└── utils/               # 通用工具
```

这是一个横向分层结构。优点是入口容易理解，缺点是业务复杂以后，所有复杂逻辑都会堆到 `services/`。

目前比较大的文件：

```text
frontend voice test hook                              1151 行
app/services/appointments/parsers.py                  815 行
app/services/twilio/official_conversational_agents.py 706 行
app/services/twilio/media_stream_bridge_service.py    687 行
app/services/appointments/operation_flow.py           648 行
app/services/live_gateway/browser_websocket_bridge.py 520 行
app/services/twilio/trace_diagnostics.py              499 行
app/services/chat_service.py                          217 行
app/services/conversation/chat_orchestrator.py        448 行
app/services/appointments/extraction_applier.py       235 行
app/services/dashboard_service.py                     216 行
app/services/twilio/incoming_service.py               583 行
app/services/twilio/media_stream_websocket_service.py 239 行
app/api/v1/endpoints/twilio_trace.py                  207 行
app/services/twilio/trace_service.py                  195 行
app/api/v1/endpoints/realtime.py                      148 行
app/services/extraction/appointment_application_service.py 147 行
app/services/twilio/status_service.py                 121 行
app/services/twilio/management_service.py             118 行
app/services/test_lab/operation_turn_service.py       117 行
app/api/v1/endpoints/twilio_incoming.py               112 行
app/api/v1/endpoints/twilio_management.py             75 行
app/api/v1/endpoints/twilio_status.py                 73 行
app/api/v1/endpoints/twilio_legacy_stream.py          23 行
app/api/v1/endpoints/dashboard.py                     19 行
app/api/v1/endpoints/prompts.py                       122 行
```

这些文件本身不是“行数大就一定错”，但它们已经暴露出职责边界不清的问题。

## 3. 已经做得比较好的地方

### 3.1 基础分层存在

`api / services / repositories / models / schemas` 已经具备，说明系统不是完全无结构。新请求大体可以按如下路径追踪：

```text
API endpoint -> Service -> Repository -> Model/DB
```

### 3.2 Twilio 子模块已有拆分意识

`app/services/twilio/` 下已经有很多职责明确的小模块，例如：

- `audio_codec.py`
- `media_stream_runtime.py`
- `manual_activity_controller.py`
- `twilio_ingress_adapter.py`
- `twilio_playback_adapter.py`
- `trace_store.py`
- `trace_diagnostics.py`
- `webhook_verification.py`

这说明 Media Stream 链路已经开始向“传输适配 + 运行时状态 + 诊断”拆分，这是正确方向。

### 3.3 测试覆盖方向正确

`backend/tests/test_services/` 已经覆盖了不少服务级单测，尤其是 Twilio runtime、trace、audio lab、operation flow helper。这对后续拆分非常重要。

## 4. 主要问题

### 4.1 `ChatService` 已降级为 facade

`ChatService` 已经移除了预约解析、复唱、匹配、执行、状态机、抽取落库、抽取编排、普通文字聊天、SSE 流式聊天和测试台 operation turn 的主要细节。它现在主要负责：

- 对外兼容 facade
- 领域服务 builder
- 保持旧 API 调用入口稳定

当前风险已经从“上帝类太大”变成“后续维护时不要把新业务逻辑写回 facade”：

- 新 helper 不应再加到 `ChatService`，应该直接进入对应领域模块。
- 如果 facade 继续膨胀到 300 行以上，应立即拆到对应 domain service。

### 4.2 API 层已完成第一轮瘦身

主要 endpoint 已经完成第一轮下沉：

- `realtime.py` 从 654 行降到 148 行。
- `twilio_legacy_stream.py` 从 196 行降到 23 行。
- `dashboard.py` 从 240 行降到 19 行。
- Twilio incoming/management/status/trace 已下沉到对应 service。

API endpoint 仍应只负责：

- 参数接收
- 鉴权/签名验证调用
- schema 转换
- 调用 service
- 返回响应

后续如果 endpoint 内再次出现长生命周期 WebSocket、音频处理、状态机、业务判断，就应该下沉到 service 或 runtime。

### 4.3 业务域目录已建立，legacy 文件仍需逐步归位

当前已经建立显式业务域：

```text
appointments/
conversation/
extraction/
test_lab/
twilio/
live_gateway/
```

仍保留的历史文件包括：

- `test_session_service.py`
- `extraction_service.py`
- `extraction_bridge.py`
- `prompt_service.py`
- `twilio_voice_agent_service.py`
- `twilio_webcall_service.py`

这些不必一次性移动。后续改到对应逻辑时，再按风险可控的方式迁移。

### 4.4 Prompt 与确定性业务逻辑边界不清

当前 Prompt 管理页面可以控制 Gemini 的自然语言行为，但不能控制后端状态机文案。这个设计本身合理，但代码结构没有把边界讲清楚。

应该明确：

- Gemini system prompt: 控制自然对话策略。
- Business confirmation template: 控制确定性业务确认文案。
- Operation executor: 控制数据库更新。

这三者不应该混在一个 `ChatService` 中。

### 4.5 文档基线已更新

`backend/docs/ARCHITECTURE.md` 和 `SERVICE_LAYER_GUIDE.md` 已更新为当前结构，内容已经对齐真实 Twilio、Gemini Live、CX/Conversational Agents、Media Streams 和 Test Lab 链路。

后续要求：

- 新领域模块落地后同步更新这两个文档。
- 回归命令变化后同步更新 bundled Node / pytest / ruff 说明。

### 4.6 API router 历史入口已收口

当前实际入口是 `app/api/routes.py`。`app/api/v1/router.py` 已改成兼容 re-export，不再维护过期的半套路由集合。

后续建议：

- 保持一个 canonical router，避免两个文件各自 include router。
- 如果未来要改为 `app/api/v1/router.py` 作为唯一入口，需要同时让 `app/api/routes.py` 变成薄 re-export，不能再分叉维护。

## 5. 推荐目标结构

不建议一次性大迁移到 DDD，否则风险太高。建议采用“保留外层横向分层 + 在 services 内按领域拆包”的渐进方案。

目标结构：

```text
backend/app/
├── api/
│   └── v1/endpoints/
│       ├── appointments.py
│       ├── chat.py
│       ├── test_lab.py
│       ├── twilio/
│       │   ├── incoming.py
│       │   ├── media_stream.py
│       │   ├── official_ca.py
│       │   ├── status.py
│       │   └── trace.py
│       └── voice.py
│
├── core/
│   ├── config.py
│   ├── database.py
│   ├── logging.py
│   └── model_defaults.py
│
├── models/
├── repositories/
├── schemas/
│   ├── appointments.py
│   ├── chat.py
│   ├── test_lab.py
│   ├── twilio.py
│   └── voice.py
│
├── services/
│   ├── appointments/
│   │   ├── extraction_applier.py
│   │   ├── operation_executor.py
│   │   ├── operation_flow.py
│   │   ├── operation_matcher.py
│   │   ├── parsers.py
│   │   └── presenter.py
│   │
│   ├── conversation/
│   │   ├── chat_orchestrator.py
│   │   ├── chat_runtime_service.py
│   │   └── transcript_sanitizer.py
│   │
│   ├── extraction/
│   │   ├── extraction_service.py
│   │   └── extraction_bridge.py
│   │
│   ├── prompt_runtime/
│   │   ├── prompt_service.py
│   │   └── runtime_resolver.py
│   │
│   ├── test_lab/
│   │   └── session_service.py
│   │
│   ├── llm/
│   ├── twilio/
│   ├── live_gateway/
│   └── voice_runtime/
│
└── utils/
```

## 6. 模块职责建议

### 6.1 `services/appointments/parsers.py`

职责：

- 日文日期解析
- 姓名/公司/电话提取
- 地址/数量/品目提取
- affirmative/negative 判断

不能做：

- 数据库查询
- LLM 调用
- FastAPI Response 构造

### 6.2 `services/appointments/presenter.py`

职责：

- 预约复唱文案
- 变更前后对比文案
- 操作完成文案
- 后续可以接入“业务确认话术模板”

不能做：

- 匹配候选预约
- 更新数据库
- 调用 Gemini

你这次问的“取消时复唱内容在哪里改”，未来应该只在这里改，而不是进 `ChatService`。

### 6.3 `services/appointments/operation_matcher.py`

职责：

- 根据 `target_appointment_id` 直接查找目标预约
- 根据姓名、公司、电话、原预约时间匹配候选
- 候选打分
- 防止匹配当前取消会话自身
- 防止重复取消已取消预约

数据库查询可以通过 `AppointmentRepository` 完成，但“打分规则”应放在 matcher，而不是 repo。

### 6.4 `services/appointments/operation_executor.py`

职责：

- 执行取消
- 执行变更
- 更新原预约 `extra_data.lifecycle_status`
- 创建 operation event
- 写入 `operation_execution`

这是强业务一致性模块，应有独立单测。

### 6.5 `services/appointments/operation_flow.py`

职责：

- 修改/取消状态机
- `idle -> await_target_input -> await_target_confirmation -> await_update_payload -> await_execute_confirmation`
- 调用 matcher、presenter、executor

不能做：

- LLM 自由对话
- 音频链路处理
- 前端测试页面状态管理

### 6.6 `services/appointments/extraction_applier.py`

职责：

- 接收 LLM extraction result
- 判断 `request_type = new/update/cancel`
- new: 创建预约
- update/cancel: 匹配目标预约并执行 operation
- 匹配失败时返回明确失败，不伪装成新预约

这正是最近取消记录误变成 `create` 的根源位置，应该独立出来。

### 6.7 `services/conversation/chat_orchestrator.py`

职责：

- 普通文字聊天
- 流式文字聊天
- 调用 operation flow 或 LLM
- 调用 message runtime 持久化

它应该是编排层，不应该自己解析日文日期、不应该自己创建预约。

### 6.8 `test_session_service.py` / `services/test_lab/`

职责：

- 测试页面 start/finalize
- 追加测试 transcript
- 调用 extraction bridge

当前 `test_session_service.py` 已经相对独立，建议移动到 `services/test_lab/`。

### 6.9 `services/twilio/`

职责：

- Twilio webhook/TwiML/Media Streams 的传输逻辑
- 音频编解码
- Gemini Live session adapter
- trace/diagnostics
- playback/barge-in/manual activity

原则：

- Twilio 模块不应该直接理解“取消预约如何匹配目标预约”。
- Twilio 只应该在业务完成时调用统一的 appointment/conversation application service。

## 7. 推荐依赖方向

应该保持单向依赖：

```text
api
  -> services
      -> repositories
          -> models

services/conversation
  -> services/appointments
  -> services/llm
  -> services/prompt_runtime

services/twilio
  -> services/voice_runtime
  -> services/live_gateway
  -> services/conversation 或 services/appointments 的明确入口
```

禁止方向：

```text
repositories -> services
models       -> services
schemas      -> services
services/appointments -> api
services/twilio/audio_codec -> appointments
```

## 8. 分阶段落地计划

### Phase 0: 冻结行为，补齐测试

目标：

- 先不重构逻辑，只补关键行为测试。
- 覆盖新建、取消、变更、抽取失败、目标匹配失败、已取消预约重复取消。

验收：

- 当前直连语音取消场景有回归测试。
- `request_type=cancel` 不再创建 `operation=create` 预约。
- 旧接口响应结构不变。

### Phase 1: 先拆纯函数

优先拆不会碰数据库的模块：

- `JapaneseAppointmentParser`
- `AppointmentBriefPresenter`
- transcript sanitizer 已有，可继续保留或移动到 `conversation/`

风险低，因为纯函数最容易测。

验收：

- `ChatService` 中的解析/格式化 helper 大幅减少。
- 原有 helper 单测迁移到对应测试文件。

### Phase 2: 拆预约操作业务

拆出：

- `AppointmentOperationMatcher`
- `AppointmentOperationExecutor`
- `AppointmentOperationFlowService`

验收：

- `ChatService._handle_appointment_operation_flow()` 被替换成 `operation_flow.advance(call, user_message)`。
- `ChatService` 不再直接创建 operation event。
- operation flow 单测不依赖完整 `ChatService`。

### Phase 3: 拆 extraction applier

状态：已完成。

拆出：

- `AppointmentExtractionApplier`

验收：

- `ChatService.extract_appointment()` 只做编排：
  1. 获取 call
  2. 获取 messages
  3. 调 extraction service
  4. 调 applier
  5. 返回 response

### Phase 4: 收缩 ChatService

状态：核心目标已完成。`process_chat()` / `stream_chat()` 已委托 `ConversationOrchestrator`，`process_test_session_operation_turn()` 已委托 `TestSessionOperationTurnService`，`extract_appointment()` 已委托 `AppointmentExtractionApplicationService`。

目标：

- `ChatService` 从 2415 行收缩到 300-500 行。
- 只作为 facade/orchestrator 保留对外 API。

保留方法：

- `process_chat`
- `stream_chat`
- `extract_appointment`
- `process_test_session_operation_turn`
- `start_test_session`
- `finalize_test_session`

但这些方法内部只调用其他服务，不直接做解析、匹配、落库细节。

### Phase 5: 整理 API router 与 endpoints

状态：主体已完成。API router 入口已统一，`realtime.py` 的 Live Gateway 运行时已下沉到 `services/live_gateway/`；Twilio trace、incoming、management、status、media stream WebSocket 入口已下沉到 `services/twilio/` 对应 service；Dashboard 统计查询已下沉到 `DashboardService`；Prompt 模板写操作已收敛到 `PromptService`。

目标：

- 统一实际入口：`app/api/routes.py` 或 `app/api/v1/router.py` 二选一。
- Twilio endpoints 可以按子目录拆分。
- `realtime.py` 中长逻辑下沉 service。

验收：

- endpoint 文件只负责 HTTP/WebSocket 边界。
- service 文件承担业务/运行时逻辑。
- 当前剩余较厚 endpoint 主要是非 Twilio 的 `chat.py`；Twilio endpoint、Dashboard endpoint 和 Prompt 写操作主体已经基本变薄。

### Phase 6: 更新文档

状态：当前基线已完成。

已更新：

- `backend/docs/ARCHITECTURE.md`
- `backend/docs/SERVICE_LAYER_GUIDE.md`
- `backend/docs/VOICE_GATEWAYS.md`
- `backend/docs/MEDIA_STREAM_TRACE_FIELDS.md`
- `backend/docs/APPOINTMENT_OPERATION_FLOW.md`
- `backend/docs/BUSINESS_TEMPLATE_DESIGN.md`

后续可继续细化：如果要真正落地 BusinessTemplate，需要新增 renderer/resolver、测试和前端配置 UI。

## 9. 推荐测试结构

目标结构：

```text
backend/tests/
├── test_api/
├── test_services/
│   ├── appointments/
│   │   ├── test_operation_flow.py
│   │   ├── test_operation_matcher.py
│   │   ├── test_operation_executor.py
│   │   ├── test_extraction_applier.py
│   │   └── test_presenter.py
│   ├── conversation/
│   │   ├── test_chat_orchestrator.py
│   │   └── test_chat_runtime_service.py
│   ├── test_lab/
│   │   └── test_session_service.py
│   ├── twilio/
│   └── llm/
└── test_integration/
```

关键回归用例：

- 新规预约正常创建。
- 取消请求不会创建新预约。
- 取消请求能把目标预约标记为 `cancelled`。
- 变更请求能把目标预约标记为 `latest_operation_type=update`。
- 目标匹配失败时返回可解释失败。
- 同名同日多个预约时必须进入 disambiguation。
- Twilio Media Stream 音频桥不依赖 appointment operation 内部类。

## 10. 命名规范建议

### 文件命名

使用“名词 + 角色”：

- `operation_flow.py`
- `operation_matcher.py`
- `operation_executor.py`
- `extraction_applier.py`
- `presenter.py`
- `parsers.py`
- `chat_orchestrator.py`

避免：

- `helpers.py`
- `utils.py`
- `manager.py`
- `service2.py`

### 类命名

```python
AppointmentOperationFlowService
AppointmentOperationMatcher
AppointmentOperationExecutor
AppointmentExtractionApplier
AppointmentBriefPresenter
JapaneseAppointmentParser
ConversationOrchestrator
```

## 11. Prompt 管理与业务模板的边界

建议后续增加“业务确认话术模板”，不要把它混进 Gemini Prompt。

建议配置层级：

```text
PromptTemplate
  - system_prompt
  - extraction_prompt
  - extraction_schema
  - live model / voice config

BusinessTemplate
  - appointment_brief_template
  - cancel_confirmation_template
  - update_confirmation_template
  - operation_complete_template
```

这样可以做到：

- Prompt 控制自然语言对话策略。
- BusinessTemplate 控制确定性业务复唱。
- Executor 控制实际数据库更新。

这比“让 Gemini 自己决定怎么复唱并顺便更新 DB”更安全。

## 12. 新人接手时的理想阅读路径

目标是让新人按这个顺序读代码：

1. `backend/docs/BACKEND_ARCHITECTURE_REVIEW.md`
2. `backend/docs/ARCHITECTURE.md`
3. `app/api/routes.py`
4. `app/api/v1/endpoints/chat.py`
5. `services/conversation/chat_orchestrator.py`
6. `services/appointments/operation_flow.py`
7. `services/appointments/operation_executor.py`
8. `services/twilio/media_stream_bridge_service.py`
9. `tests/test_services/appointments/`
10. `tests/test_services/twilio/`

当前第 5-10 步已经有明确模块；下一步建议只在有实际产品需求时实现 BusinessTemplate renderer/resolver。

## 13. 优先级建议

### P0: 必须做

- 保证新增预约、取消、变更的所有入口继续只通过 appointments 域服务落库。
- 防止新的业务逻辑回流到 `ChatService` 或 endpoint。
- 保持路由、预约落库、浏览器直连 Gemini、Twilio 回调回归测试稳定。

### P1: 应该做

- 按 `BUSINESS_TEMPLATE_DESIGN.md` 实现 BusinessTemplate renderer/resolver。

### P2: 可以后续做

- 将 `api/v1/endpoints/twilio_*.py` 迁移到 endpoint 子目录。
- 将 `schemas/chat.py` 拆成 `chat.py / test_lab.py / extraction.py`。
- 建立 `test_integration/` 做跨服务用例。

## 14. 最终目标

重构完成后，应该达到：

- 新人看到目录就能知道每块逻辑在哪里。
- 改复唱文案不用进 `ChatService`。
- 改 Gemini Prompt 不会误以为能改数据库操作。
- Twilio 音频链路和预约业务逻辑解耦。
- 取消/变更的目标匹配、确认、执行有独立测试。
- `ChatService` 只是薄编排层，不再是 2000 行上帝类。
