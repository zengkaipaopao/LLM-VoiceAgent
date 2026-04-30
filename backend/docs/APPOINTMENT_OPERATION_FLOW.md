# 预约变更与取消状态机

最后更新: 2026-04-30

## 1. 目标

本文档说明预约变更、取消为什么不完全交给 Gemini Prompt 控制，以及后端确定性状态机如何工作。

原则：

- Gemini 负责自然语言理解和对话表达。
- 后端负责目标预约匹配、复唱、最终确认和数据库更新。
- Prompt 可以影响模型怎么问，但不能直接决定数据库如何改。

## 2. 关键模块

```text
app/services/appointments/parsers.py
app/services/appointments/presenter.py
app/services/appointments/operation_matcher.py
app/services/appointments/operation_flow.py
app/services/appointments/operation_executor.py
app/services/appointments/extraction_applier.py
```

职责划分：

- `JapaneseAppointmentParser`: 从日文转写文本中提取姓名、公司、电话、日期、地址、数量、品目和肯定/否定意图。
- `AppointmentBriefPresenter`: 生成确定性复唱文案。
- `AppointmentOperationMatcher`: 根据姓名、电话、公司、预约时间、目标 ID 匹配原预约。
- `AppointmentOperationFlowService`: 推进多轮状态机。
- `AppointmentOperationExecutor`: 最终确认后执行取消或变更，并创建 operation event。
- `AppointmentExtractionApplier`: 通话结束后根据 LLM extraction 兜底创建/变更/取消预约。

## 3. 状态流

当前核心状态流：

```text
idle
-> await_target_input
-> await_target_confirmation
-> await_update_payload
-> await_execute_confirmation
-> executed
```

取消通常走：

```text
cancel intent
-> collect target hints
-> match target appointment
-> repeat target summary
-> user confirms
-> mark original appointment cancelled
-> create cancel operation event
```

变更通常走：

```text
update intent
-> collect target hints
-> match target appointment
-> collect new payload
-> repeat before/after summary
-> user confirms
-> mark original appointment updated
-> create update operation event
```

## 4. 复唱内容在哪里改

复唱内容优先改：

```text
app/services/appointments/presenter.py
app/services/appointments/operation_flow.py
```

不要改：

```text
app/services/chat_service.py
app/api/v1/endpoints/chat.py
```

原因：

- 复唱属于业务确定性文案，不是 API 边界。
- 复唱需要和目标匹配、最终确认状态一致。
- 如果散落在 Prompt 或 endpoint 中，取消/变更很容易再次出现状态和落库不一致。

## 5. Prompt 的作用边界

Prompt 可以要求模型：

- 用丁寧语。
- 一次只问一个问题。
- 不要在最终确认前使用确定表达。
- 提醒需要确认日期、地址、数量。

Prompt 不应该承担：

- 查找目标预约。
- 判断多候选预约哪个应该取消。
- 修改 `lifecycle_status`。
- 创建 operation event。
- 决定最终数据库写入。

## 6. 数据库写入规则

取消成功时：

- 原预约保留。
- 原预约 `extra_data.lifecycle_status` 标记为 `cancelled`。
- 创建一条 `operation=cancel` 的操作事件。
- 操作事件记录 `target_appointment_id` 和执行结果。

变更成功时：

- 原预约保留。
- 原预约记录变更状态，例如 `latest_operation_type=update`。
- 创建一条 `operation=update` 的操作事件。
- 操作事件记录变更后的字段和执行结果。

这样预约管理页面可以通过原预约状态显示红色取消或蓝色变更，同时保留操作审计记录。

## 7. 测试入口

关键单测：

```text
tests/test_services/appointments/test_appointment_parser_presenter.py
tests/test_services/appointments/test_appointment_operation_matcher.py
tests/test_services/appointments/test_appointment_operation_executor.py
tests/test_services/appointments/test_appointment_operation_flow.py
tests/test_services/appointments/test_appointment_extraction_applier.py
tests/test_services/extraction/test_appointment_extraction_application_service.py
tests/test_services/test_lab/test_test_lab_operation_turn_service.py
```

关键回归：

- 取消请求不会创建新预约。
- 取消成功后原预约能被标记为 cancelled。
- 变更成功后原预约能被标记为 updated。
- 匹配失败时返回明确失败，不伪装成新预约。
- 同名同日多个候选时不能静默执行。

## 8. 后续优化

可以新增 `BusinessTemplate`，让确定性复唱文案可配置：

```text
BusinessTemplate
  - appointment_brief_template
  - cancel_confirmation_template
  - update_confirmation_template
  - operation_complete_template
```

但即使文案可配置，执行逻辑仍应该保留在后端状态机和 executor 中。

配置化设计详见：

```text
backend/docs/BUSINESS_TEMPLATE_DESIGN.md
```
