# 后端架构审视与改善方案

最后更新: 2026-04-27

## 1. 结论

当前后端已经有基础分层结构：`api -> services -> repositories -> models/schemas`。这个方向是对的，Twilio Media Streams 相关代码也已经比早期更模块化。但是业务领域边界还不够清晰，尤其是 `app/services/chat_service.py` 目前承担了过多职责，已经成为后端可维护性的主要风险点。

当前最需要治理的不是“重写系统”，而是把已经混在一起的职责拆回明确的领域模块，让新接手的人可以通过目录名理解系统：

- 电话/浏览器语音链路属于传输层和实时会话层。
- Gemini/LLM 调用属于模型适配层。
- 预约创建、变更、取消属于预约业务域。
- 测试页面会话属于 test lab 域。
- Prompt 模板是配置和运行时解析域，不应该承载确定性数据库操作逻辑。

## 1.1 当前落地状态

截至 2026-04-27，Phase 1 已开始落地：

- 已新增 `app/services/appointments/parsers.py`，集中维护日文预约文本解析、ASR 空格日期解析、姓名/公司/电话/数量/地址提取、目标匹配打分辅助逻辑。
- 已新增 `app/services/appointments/presenter.py`，集中维护预约复唱文案格式化。
- 已新增 `app/services/appointments/operation_matcher.py`，集中维护预约变更/取消的目标候选查询与匹配。
- 已新增 `app/services/appointments/operation_executor.py`，集中维护确认后的预约更新/取消、操作事件创建、`operation_execution` 写回。
- 已新增 `app/services/appointments/operation_flow.py`，集中维护预约变更/取消的多状态对话流。
- `ChatService` 已通过兼容别名调用上述模块，原解析/复唱实现已从 `chat_service.py` 删除。
- `ChatService` 的目标匹配、执行动作、多状态对话流已通过兼容入口委托到 appointment domain 模块。
- `chat_service.py` 已从 2415 行收缩到 927 行。
- 已新增 `tests/test_services/test_appointment_parser_presenter.py`、`test_appointment_operation_matcher.py`、`test_appointment_operation_executor.py`、`test_appointment_operation_flow.py` 覆盖新模块。
- 已修复 Test Lab 直连语音会话结束收口：`finalize_test_session()` 现在会复制 JSON 后写入 `finalized_at / appointment_id / extraction_status`，避免 SQLAlchemy JSON 字段未被判定 dirty。
- 已在前端直连语音页增加离开页面时的静默 finalize，避免用户从语音测试页直接切到预约管理时，会话没有统一完成抽取。

下一步建议进入 Phase 3：拆 `ExtractionApplicationService`，让最终抽取后的预约创建/变更/取消兜底不再留在 `ChatService.extract_appointment()` 中。

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
app/api/v1/endpoints/realtime.py                      654 行
app/services/twilio/trace_diagnostics.py              499 行
app/services/chat_service.py                          927 行
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

### 4.1 `ChatService` 是当前最大上帝类

`ChatService` 现在同时负责：

- 文字聊天编排
- 流式聊天编排
- Gemini/LLM 调用和 quota fallback
- 测试会话 start/finalize
- transcript/message 清洗
- 冗余开场白清理
- 预约信息抽取
- 新预约落库
- 修改/取消状态机
- 目标预约匹配
- 日文姓名/公司/日期/地址/数量解析
- 预约复唱文案格式化
- 操作事件创建

这导致几个现实问题：

- 修改“复唱文案”需要进入 2000 多行服务文件。
- 修改取消逻辑可能影响文字测试、浏览器直连、电话后处理。
- 新人无法从文件名判断某段逻辑属于聊天、预约、抽取还是测试系统。
- 单测只能围绕 `test_chat_service_helpers.py` 堆积，测试命名也会越来越模糊。

### 4.2 API 层仍有偏厚 endpoint

`app/api/v1/endpoints/realtime.py` 已经 654 行。API endpoint 应该主要负责：

- 参数接收
- 鉴权/签名验证调用
- schema 转换
- 调用 service
- 返回响应

如果 endpoint 内有长生命周期 WebSocket、音频处理、状态机、业务判断，就应该下沉到 service 或 runtime。

### 4.3 业务域没有显式目录

目前 `services/` 是按技术或历史命名混放：

```text
chat_service.py
test_session_service.py
extraction_service.py
extraction_bridge.py
prompt_service.py
twilio/
llm/
voice_runtime/
live_gateway/
```

但是系统真实业务域至少有这些：

- `appointments`: 预约创建、变更、取消、匹配、复唱、落库
- `conversation`: 文本/语音对话编排、消息持久化、transcript 清洗
- `voice_gateway`: Twilio、浏览器直连、CX/CA、Media Stream
- `prompt_runtime`: Prompt 模板解析、模型/音色配置
- `test_lab`: 测试页面会话生命周期、离线音频实验、trace

这些业务域没有明确落在目录上，所以维护者只能靠搜索和记忆。

### 4.4 Prompt 与确定性业务逻辑边界不清

当前 Prompt 管理页面可以控制 Gemini 的自然语言行为，但不能控制后端状态机文案。这个设计本身合理，但代码结构没有把边界讲清楚。

应该明确：

- Gemini system prompt: 控制自然对话策略。
- Business confirmation template: 控制确定性业务确认文案。
- Operation executor: 控制数据库更新。

这三者不应该混在一个 `ChatService` 中。

### 4.5 文档部分已经过期

`backend/docs/ARCHITECTURE.md` 和 `SERVICE_LAYER_GUIDE.md` 仍有“Simulation 阶段”“等待 SIP 集成”的描述，但项目现在已经有 Twilio、Gemini Live、CX/Conversational Agents、Media Stream、Test Lab。

这会误导新接手的人，以为系统还停留在模拟数据阶段。

### 4.6 API router 存在历史入口

当前实际入口是 `app/api/routes.py`，而 `app/api/v1/router.py` 只 include 了早期模拟和 calls 路由。这个文件如果继续存在但不作为真实入口，会让新人困惑。

建议后续选择一种：

- 删除/废弃 `app/api/v1/router.py`。
- 或让 `app/api/v1/router.py` 成为唯一 v1 聚合入口，`app/api/routes.py` 只负责挂载版本前缀。

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
│   │   ├── message_runtime.py
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

### 6.8 `services/test_lab/session_service.py`

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

- `AppointmentTextParser`
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

目标：

- 统一实际入口：`app/api/routes.py` 或 `app/api/v1/router.py` 二选一。
- Twilio endpoints 可以按子目录拆分。
- `realtime.py` 中长逻辑下沉 service。

验收：

- endpoint 文件只负责 HTTP/WebSocket 边界。
- service 文件承担业务/运行时逻辑。

### Phase 6: 更新文档

需要更新：

- `backend/docs/ARCHITECTURE.md`
- `backend/docs/SERVICE_LAYER_GUIDE.md`
- 新增或更新 voice/media stream 链路文档
- 新增 appointment operation flow 文档

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
│   │   └── test_message_runtime.py
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
ChatOrchestrator
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

当前最大问题是第 5-7 步都被压在 `chat_service.py` 里。

## 13. 优先级建议

### P0: 必须做

- 把 `ChatService` 的预约操作相关逻辑拆出来。
- 保证取消/变更的状态机与最终抽取兜底共用同一个 executor。
- 更新架构文档，避免文档继续停留在 simulation 阶段。

### P1: 应该做

- 拆 `AppointmentBriefPresenter`，让复唱文案有明确位置。
- 拆 `JapaneseAppointmentParser`，让语音 ASR 规则集中维护。
- 统一 API router 入口。

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
