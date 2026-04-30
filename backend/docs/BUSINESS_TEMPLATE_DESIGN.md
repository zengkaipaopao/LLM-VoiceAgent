# BusinessTemplate 设计草案

最后更新: 2026-04-30

## 1. 背景

当前 PromptTemplate 控制 Gemini 的自然语言行为，但预约变更/取消的确定性复唱、最终确认和完成话术由后端状态机生成。

这个边界是正确的：

- PromptTemplate 适合控制“模型怎么对话”。
- BusinessTemplate 适合控制“业务确认文案怎么说”。
- Executor 负责“数据库实际怎么改”。

如果把确定性复唱放进 Prompt，会出现两个风险：

- 模型可能省略关键字段，导致用户确认不完整。
- 模型话术和后端实际落库状态可能不一致。

## 2. 目标

BusinessTemplate 的目标是让业务确认话术可配置，同时不破坏后端确定性状态机。

应该支持：

- 新预约最终复唱。
- 取消目标复唱。
- 变更前后对比复唱。
- 操作完成文案。
- 多语言版本。
- 按 PromptTemplate 或业务场景绑定。

不应该支持：

- 通过模板决定是否更新数据库。
- 通过模板选择目标预约。
- 通过模板绕过最终确认。
- 让模型自由生成 operation event。

## 3. 建议数据结构

### 表：`business_templates`

建议字段：

```text
id UUID primary key
code varchar unique
name varchar
language varchar
appointment_brief_template text
cancel_confirmation_template text
update_confirmation_template text
operation_complete_template text
metadata jsonb
is_active boolean
created_at timestamp
updated_at timestamp
```

### PromptTemplate 绑定方式

短期方案：

```text
prompt_templates.metadata.business_template_code
```

长期方案：

```text
prompt_templates.business_template_id -> business_templates.id
```

短期先用 metadata，避免立即迁移 schema 和前端表单。

## 4. 模板变量

建议使用明确白名单变量，不允许任意 Python 表达式。

预约变量：

```text
{appointment_time}
{caller_name}
{company}
{category}
{amount}
{address}
{extra_request}
```

变更变量：

```text
{before_summary}
{after_summary}
{changed_fields}
```

操作变量：

```text
{operation_label}
{target_summary}
```

缺失值策略：

- 缺失字段显示 `未確認` 或配置化 fallback。
- 不允许因为字段缺失而静默省略关键确认项。
- 如果最终确认所需字段缺失，状态机应继续追问，而不是渲染确认文案。

## 5. 服务边界

建议新增：

```text
app/services/appointments/business_template_renderer.py
app/services/appointments/business_template_resolver.py
```

职责：

- `BusinessTemplateResolver`: 根据 PromptTemplate metadata、语言、默认配置解析模板。
- `BusinessTemplateRenderer`: 安全替换变量，处理缺失值和格式化。

现有模块调整：

```text
AppointmentBriefPresenter
-> 使用 BusinessTemplateRenderer
-> 没有配置时使用当前硬编码默认文案
```

不要调整：

```text
AppointmentOperationExecutor
```

Executor 只管实际状态更新，不应该被话术模板影响。

## 6. 渐进实施顺序

### Phase 1: Renderer 纯函数

新增 renderer，不接数据库。

验收：

- 默认模板渲染结果和当前 `AppointmentBriefPresenter` 输出一致。
- 缺失字段 fallback 有单测。
- 不影响现有 Prompt 管理页面。

### Phase 2: Resolver 接 Prompt metadata

从 `prompt_templates.metadata.business_template_code` 解析模板。

验收：

- 没配置时完全走默认文案。
- 配置了 code 但找不到模板时记录 warning，并 fallback 默认文案。

### Phase 3: 管理页面配置

前端 Prompt 管理页增加“业务确认话术模板”区域。

验收：

- 用户可以编辑复唱文案。
- 不能编辑数据库执行规则。
- 模板预览可以显示样例预约。

### Phase 4: 独立表

如果配置变多，再迁移到 `business_templates` 表。

## 7. 测试要求

新增测试：

```text
tests/test_services/appointments/test_business_template_renderer.py
tests/test_services/appointments/test_business_template_resolver.py
```

关键用例：

- 默认模板与当前复唱文案兼容。
- 地址、数量、品目都能出现在取消确认复唱中。
- 缺失字段不会导致 KeyError。
- 非白名单变量不会执行。
- 找不到模板时 fallback 默认文案。

## 8. 与 PromptTemplate 的关系

PromptTemplate 继续控制：

- system prompt。
- extraction prompt/schema。
- LLM provider/model。
- Gemini Live voice。
- 默认 Twilio route metadata。

BusinessTemplate 控制：

- 后端确定性复唱。
- 后端最终确认话术。
- 操作完成固定文案。

两者共同服务同一业务场景，但不能互相替代。
