# 项目阶段与 TODO 清单

最后更新: 2026-05-25

## 1. 当前阶段判断

项目当前处于 **电话主链路稳定化攻坚阶段 / 上云前置阻塞阶段**。

判断依据：

- 后端核心分层已形成，存在 API、Service、Repository、Schema、Model、Alembic。
- 前端管理台页面和测试台已具备可用雏形。
- Gemini 文本、Gemini Live 浏览器直连、Twilio 入站、Media Streams 框架、官方 CX 对照链路均已有实现。
- 浏览器直连已经能证明 Gemini Live、Prompt 和浏览器音频链路基本可用，但不能代表电话主链路已经可交付。
- 自建 Twilio Media Streams + Gemini Live 是产品主路径，目前第二轮后处理/turn state 仍未稳定，是上云前最高优先级阻塞项。
- 通话、预约、Prompt 三类核心数据已持久化。
- 预约操作流和 Twilio 诊断链路已有较多自动化测试。
- 官方 Conversational Agents/CX Agent Studio 只能作为对照或 fallback；由于需要在 Google 平台维护流程和参数，无法替代本地 PromptTemplate 动态切换主链路。
- 在电话主链路稳定前，Redis runtime store、云部署、Secret Manager、监控告警等生产化工作都应排在其后。

## 2. 已完成能力

### 2.1 后端

- FastAPI 应用入口、统一异常处理、request_id 日志。
- API Key 管理接口保护机制。
- PostgreSQL + SQLAlchemy + Alembic。
- calls、appointments、prompt_templates 数据模型。
- PromptTemplate CRUD 和 runtime 解析。
- Gemini 文本对话与结构化抽取。
- 浏览器直连 Gemini Live WebSocket。
- Twilio 入站 webhook、TwiML、Media Streams WebSocket 框架。
- Twilio μ-law/PCM 转码、trace、diagnostics、audio lab。
- 预约 create/update/delete 操作流。
- 单元测试和服务测试覆盖主要业务模块。

### 2.2 前端

- React 18 + TypeScript + Vite 工程。
- IBM Carbon UIShell 和页面布局。
- Dashboard、Calls、Appointments、Prompts、Test、Settings 页面。
- Prompt 编辑器和列表。
- 通话/预约数据表。
- 统一测试台，覆盖文本、浏览器语音、Twilio 相关调试入口。
- i18n 支持 zh-CN、en-US、ja-JP。
- 若干 hook 和工具函数测试。

### 2.3 文档

- 架构文档。
- Twilio/Gemini 语音专项设计。
- 后端 API、数据库、配置、开发规范文档。
- 前端 API 契约和项目结构文档。
- 本次新增交接文档集。
- 上云准备与后端风险交接文档。

## 3. 主要风险

| 风险 | 影响 | 建议 |
| --- | --- | --- |
| Twilio + Gemini Live 自建 Media Streams 主链路未稳定 | 真实电话座席无法可靠多轮对话，系统不能进入上云生产化 | P0-00：优先修复第二轮后处理/turn state，并完成真实电话多轮验收 |
| 官方 CA 无法承载本地 PromptTemplate 动态切换 | Prompt、抽取 schema、业务落库会和本系统配置体系割裂 | 官方 CA 仅作为对照/fallback，不作为主产品路径 |
| runtime store 默认 memory | 多进程/多实例时 Twilio stream state 不共享 | 主链路稳定后再推进 Redis runtime store 并压测 |
| 生产认证授权较薄 | 管理台 API 只有 API Key，不满足企业权限审计 | P0/P1：补 RBAC 或接入 IdP |
| Twilio 自建桥接需生产压测 | 高并发和弱网下可能出现延迟、断流、回合卡死 | 主链路单通话多轮稳定后，建立压测和 trace 验收基线 |
| debug wav 默认开发友好 | 生产可能带来存储和隐私风险 | P0：生产关闭或接对象存储与保留策略 |
| LLM 供应商抽象未完全产品化 | 多供应商切换可能停留在接口层 | P1：明确 provider contract 和兼容测试 |
| 前端 API 运行时校验需要持续推进 | 接口变更可能引入隐式字段错配 | P1：按 API 契约补齐 Zod mapper |
| 缺少 CI/CD 与部署基线 | 交付质量依赖人工操作 | P1：增加 GitHub Actions 和环境发布手册 |

详细上云风险、环境变量矩阵和后端排障路径见：[上云准备与后端风险交接说明书](./06_CLOUD_READINESS_AND_BACKEND_RISKS.md)。

## 4. TODO 优先级

### P0：MVP / 上云前阻塞项

| 编号 | TODO | 验收标准 |
| --- | --- | --- |
| P0-00 | 稳定 Twilio + Gemini Live 自建 Media Streams 电话主链路 | 真实电话下可连续 5-10 轮对话；第二轮、第三轮用户发话后 Gemini 能继续识别和回复；通话不中断、不挂死 |
| P0-01 | 修复第二轮后处理/turn state 问题 | trace 能显示第二轮 inbound audio、input transcript、model response、outbound media、turn complete/interrupted；不误发 `audio_end`；不混用 auto/manual activity |
| P0-02 | 实现本地 PromptTemplate 在 Twilio 主链路的动态切换 | 支持按 query、号码映射、默认模板选择 Prompt；无需在 Google CA 平台手工维护业务流程即可切换系统 Prompt/模型/音色/抽取 schema |
| P0-03 | 固化 Twilio 主链路排障证据 | 每轮都有 call_sid/stream_sid/session_id、inbound chunk、Gemini event、outbound media、clear/interrupted 的 trace |
| P0-04 | 完善 barge-in 回归测试 | interrupted 后 outbound queue 清空、Twilio clear 发出、旧回复停止、后续回合可继续 |
| P0-05 | 通话结束 finalize 与预约抽取落库 | 真实 Twilio 通话结束后 transcript 可 finalize，call/appointment 可落库，失败时有明确 trace/error |
| P0-06 | 建立 Twilio Media Streams 单通话长轮次验收脚本/checklist | 至少覆盖普通多轮、用户打断、长静音、用户连续说话、通话结束 |
| P0-07 | 主链路稳定后再实现 Redis 版 runtime/trace 共享状态或明确单实例部署限制 | 多 worker/多实例下同一 call_sid/stream_sid 可正确读取状态；若暂不实现，文档明确只能单实例部署 |
| P0-08 | 生产环境安全配置基线 | CORS、API Key、Twilio 签名、Google ADC/IAM 均有检查项 |
| P0-09 | 关闭或治理生产 debug audio | 生产不会无限落本地音频文件，具备保留/脱敏策略 |
| P0-10 | 明确部署拓扑 | 单实例/多实例、反向代理、WebSocket timeout、健康检查文档化 |

### P1：交付质量增强

| 编号 | TODO | 验收标准 |
| --- | --- | --- |
| P1-01 | 增加 CI：后端 pytest、前端 build/test/i18n check | PR 自动运行并阻断失败 |
| P1-02 | 前端 API 层全面补齐 Zod 校验和 DTO mapper | 页面不直接消费 snake_case 或 legacy 字段 |
| P1-03 | 增加 OpenAPI/接口契约导出流程 | 前后端接口变更可审查 |
| P1-04 | 完善 Dashboard 指标来源 | 指标定义、SQL/Service 来源、刷新策略明确 |
| P1-05 | 增加通话详情中的 trace 跳转 | 从 call 记录可定位到 Twilio trace |
| P1-06 | 完善 Prompt 版本管理 | 支持复制、回滚、启停、默认入站模板管理 |
| P1-07 | 增加系统级错误提示 | 前端对 Gemini/Twilio/鉴权错误给出可操作提示 |

### P2：产品能力扩展

| 编号 | TODO | 验收标准 |
| --- | --- | --- |
| P2-01 | RBAC/企业账号体系 | 用户、角色、权限、审计日志可用 |
| P2-02 | 多租户/多业务线隔离 | Prompt、号码、通话、预约按 tenant 隔离 |
| P2-03 | 录音对象存储归档 | 录音/调试音频有生命周期和访问权限 |
| P2-04 | 人工接管流程 | AI 无法处理时可转人工并记录原因 |
| P2-05 | 预约系统外部集成 | 对接 CRM/日历/业务系统 |
| P2-06 | 监控告警面板 | Grafana/Prometheus/Loki 或云监控落地 |

## 5. 下一阶段建议计划

### 阶段 A：Twilio 主链路稳定化，1-2 周

- 复现并固定第二轮后处理问题。
- 用 trace 判断第二轮 inbound audio、Gemini session、activity detection、outbound queue、interrupted/clear 的真实状态。
- 修复自建 Media Streams 多轮对话。
- 完成 5-10 轮真实电话验收。
- 确认 PromptTemplate 动态切换不依赖 Google CA 平台流程。

### 阶段 B：交接稳定化，1 周

- 新同事按交接文档跑通本地。
- 修复文档和启动流程中的遗漏。
- 建立基础 CI。
- 整理 `.env.example` 与实际 Settings 的差异。

### 阶段 C：语音链路生产化，2-3 周

- Redis runtime store。
- Twilio Media Streams 压测。
- barge-in 和 turn boundary 回归。
- debug audio 治理。
- 生产 WebSocket timeout 和反向代理配置。

### 阶段 D：业务闭环强化，2-3 周

- Prompt 版本管理。
- 预约变更/取消的业务验收样例库。
- 前端通话详情、预约详情、trace 联动。
- 失败会话人工复核流程。

### 阶段 E：企业化能力，持续推进

- RBAC/SSO。
- 审计日志。
- 多租户。
- 监控告警。
- 云端 IaC 和发布流水线。

## 6. 交接验收清单

交接完成前建议确认：

- [ ] 接手同事可以独立启动前后端和数据库。
- [ ] 接手同事可以解释三条语音链路的边界。
- [ ] 接手同事明确官方 CA 只是对照/fallback，自建 Media Streams 才是产品主链路。
- [ ] 接手同事可以复现或验证 Twilio 第二轮问题，并知道应查看哪些 trace 字段。
- [ ] 接手同事可以新增一个 Prompt 并用于测试。
- [ ] 接手同事可以从一次测试会话追踪到 call/appointment 数据。
- [ ] 接手同事可以定位 Twilio trace 和 debug wav。
- [ ] 项目负责人确认 P0 TODO 的 owner 和排期。
- [ ] 文档中的命令、路径、配置与当前代码一致。
