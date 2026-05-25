# 需求分析说明书

最后更新: 2026-05-25

## 1. 背景

企业电话接待、预约登记、预约变更和取消等场景通常依赖人工坐席。系统目标是通过实时语音 AI 座席降低人工接听压力，并把通话内容结构化沉淀为可查询、可处理的业务记录。

当前项目已经从早期单体骨架发展到具备管理台、Prompt 模板、浏览器语音测试、Twilio 电话接入、Gemini Live 实时对话、预约抽取与诊断能力的开发阶段。

## 2. 项目目标

### 2.1 业务目标

- 支持电话或浏览器语音方式与 AI 座席实时对话。
- 自动识别并记录预约类业务信息。
- 提供管理台查看通话、预约、Prompt、测试结果和系统状态。
- 通过 Prompt 模板支持不同业务场景、语言、模型和音色配置。
- 为生产电话入口预留安全、观测、诊断和扩展能力。

### 2.2 技术目标

- 后端采用清晰的 `API -> Service -> Repository` 分层。
- LLM、语音运行时、电话网关使用适配器/工厂模式解耦。
- 实时语音链路以非阻塞异步 I/O 为核心，降低 TTFT 和端到端延迟。
- 前端遵循 React + TypeScript + IBM Carbon 企业级 UI 规范。
- 所有关键调用具备结构化日志、trace 字段和可复现的排障入口。

## 3. 用户与角色

| 角色 | 诉求 |
| --- | --- |
| 来电用户 | 通过自然语音完成咨询、预约、变更或取消 |
| 业务运营人员 | 查看通话记录、预约结果、处理未完成事项 |
| Prompt 管理人员 | 配置不同业务 Prompt、模型、音色、抽取 schema |
| 测试/QA | 使用测试台验证文本、浏览器语音、Twilio 电话链路 |
| 开发/运维 | 部署系统、排查语音链路、维护数据库和外部服务配置 |

## 4. 功能需求

### 4.1 管理台

| 编号 | 需求 | 当前实现状态 |
| --- | --- | --- |
| FR-001 | 仪表盘展示通话统计、趋势、系统状态 | 已有页面和 API |
| FR-002 | 通话记录查询、详情查看、转写/摘要展示 | 已有基础实现 |
| FR-003 | 预约列表查询、按通话关联、处理状态更新 | 已有基础实现 |
| FR-004 | Prompt 模板列表、新建、编辑、删除 | 已有基础实现 |
| FR-005 | 多语言界面，中/英/日资源 | 已有 i18n 资源 |
| FR-006 | 统一测试台支持文本、浏览器语音、Twilio 语音路径 | 已有测试台与多条链路 |

### 4.2 实时语音与电话接入

| 编号 | 需求 | 当前实现状态 |
| --- | --- | --- |
| FR-101 | 浏览器麦克风直连后端 WebSocket 并桥接 Gemini Live | 已实现 |
| FR-102 | Twilio 入站 webhook 返回 TwiML 并接入 Media Streams | 已实现 |
| FR-103 | μ-law 8kHz 与 PCM16 采样率转换 | 已实现 |
| FR-104 | 语音 trace、debug wav、诊断接口 | 已实现基础能力 |
| FR-105 | 支持 Twilio 官方 Conversational Agents 对照链路 | 已实现入口；仅作为对照/fallback，不作为本地 PromptTemplate 主链路 |
| FR-106 | 自建 Twilio Media Streams + Gemini Live 支持稳定多轮电话对话 | P0 未完成；第二轮后处理/turn state 仍需优先修复 |
| FR-107 | 用户打断时清空播放队列并通知 Twilio clear | 已有策略模块，需要在自建主链路稳定后继续回归 |

### 4.3 LLM 与 Prompt

| 编号 | 需求 | 当前实现状态 |
| --- | --- | --- |
| FR-201 | Gemini 文本生成和结构化抽取 | 已实现 |
| FR-202 | Gemini Live 实时语音会话 | 已实现 |
| FR-203 | PromptTemplate 支持 system prompt、抽取 schema、模型、音色 | 已实现 |
| FR-204 | 入站号码到 Prompt 的映射 | 已实现配置项和字段 |
| FR-205 | 多供应商 LLM/TTS 抽象 | 有基础接口，当前主路径为 Gemini |

### 4.4 业务数据

| 编号 | 需求 | 当前实现状态 |
| --- | --- | --- |
| FR-301 | 保存通话方向、号码、状态、摘要、转写、Prompt 关联 | 已有 calls 表 |
| FR-302 | 保存预约字段、操作类型、处理状态、原始消息和抽取数据 | 已有 appointments 表 |
| FR-303 | 支持预约新建、修改、取消的匹配和执行流程 | 已有服务与测试 |
| FR-304 | 支持 Prompt 模板版本和启用状态 | 已有字段 |

## 5. 非功能需求

| 类别 | 要求 |
| --- | --- |
| 延迟 | 实时语音链路避免阻塞事件循环；Twilio inbound frame 默认 20ms 批处理；优先优化首包和回合结束延迟 |
| 并发 | WebSocket 会话需隔离 runtime state；多进程生产环境需引入共享 runtime store |
| 可靠性 | WebSocketDisconnect、Twilio/SDK 错误、LLM 配额错误需有可观测 fallback |
| 安全 | 非 local 环境限制 CORS；API Key 保护管理接口；Twilio webhook 生产验签；优先使用 GCP ADC/Vertex AI |
| 可维护性 | API endpoint 保持薄层，业务逻辑进入 service，数据库访问进入 repository |
| 可观测性 | request_id、call_sid、session_id、stream_sid、trace event 贯穿日志和诊断 |
| 可测试性 | 单元测试覆盖服务规则；浏览器直连只验证 Gemini 能力，官方 CX 只做对照，自建 Media Streams 必须作为电话主链路进行多轮回归 |

## 6. 范围边界

### 6.1 当前范围内

- 管理台基础功能。
- Prompt 模板管理。
- 文本聊天和结构化抽取。
- 浏览器实时语音测试。
- Twilio 入站和 WebCall/Media Streams 相关能力，其中自建 Media Streams 多轮稳定性仍属于当前 P0 范围。
- 通话、预约、Prompt 数据持久化。

### 6.2 当前范围外或未完成

- 完整 RBAC/企业账号体系。
- 生产级多租户隔离。
- Redis 共享 runtime store 的完整落地与压测。
- 完整录音对象存储和长期归档。
- 生产级告警、指标面板和 SLO。
- 大规模并发压测报告。
- 完整 CI/CD、IaC 和云端部署手册。

## 7. 验收口径

### 7.1 开发环境验收

1. `docker compose up -d` 后 PostgreSQL/Redis healthy。
2. 后端 `poetry run alembic upgrade head` 成功。
3. 后端 `poetry run uvicorn app.main:app --reload` 可访问 `/api/v1/health`。
4. 前端 `npm run dev` 可访问管理台。
5. Prompt 模板可增删改查。
6. 浏览器直连语音测试可完成多轮对话。
7. 预约抽取结果可落库并在预约页查看。

### 7.2 电话链路验收

1. Twilio Voice URL 指向公开 HTTPS webhook。
2. 入站电话可拿到 TwiML 并建立 Media Stream。
3. Trace 中可看到 inbound audio、Gemini response、outbound audio、turn complete/interrupted。
4. 用户打断时 Twilio 播放被 clear，后续对话可继续。
5. 通话结束后生成 call/appointment 记录或明确失败原因。
