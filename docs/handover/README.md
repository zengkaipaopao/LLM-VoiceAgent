# LLMVoiceDesk 项目交接文档集

最后更新: 2026-05-25

## 1. 文档目的

本文档集用于项目交接、后续开发接手、架构评审和阶段验收。它不是替代代码内已有的专项文档，而是把业务目标、系统边界、模块设计、详细实现、运行维护、当前 TODO、上云准备和后端风险串成一套可交接的企业级说明。

## 2. 阅读顺序

| 顺序 | 文档 | 适合读者 | 重点 |
| --- | --- | --- | --- |
| 1 | [需求分析说明书](./01_REQUIREMENTS_ANALYSIS.md) | 产品、项目经理、开发负责人 | 项目目标、业务范围、功能/非功能需求、验收口径 |
| 2 | [基本设计说明书](./02_BASIC_DESIGN.md) | 架构师、后端、前端、测试 | 总体架构、模块划分、数据流、外部系统边界 |
| 3 | [详细设计说明书](./03_DETAILED_DESIGN.md) | 后端、前端、测试、运维 | API、服务、数据库、实时语音链路、错误处理 |
| 4 | [运维与交接说明书](./04_OPERATIONS_AND_HANDOVER.md) | 接手开发、运维、测试 | 本地启动、配置、部署、安全、排障、发布检查 |
| 5 | [项目阶段与 TODO 清单](./05_PROJECT_STATUS_AND_TODO.md) | 项目负责人、接手团队 | 当前完成度、风险、优先级、下一阶段计划 |
| 6 | [上云准备与后端风险交接说明书](./06_CLOUD_READINESS_AND_BACKEND_RISKS.md) | 后端、云工程、运维负责人 | 云上目标架构、后端风险、环境变量、排障路径、上云验收 |

## 3. 项目一句话概述

LLMVoiceDesk 是一个面向企业电话接待和预约处理场景的实时语音 AI 座席系统。系统通过浏览器直连或 Twilio 电话网关接入语音流，后端使用 FastAPI 编排 Gemini Live/LLM、Prompt、通话、预约抽取和诊断链路，前端使用 React + TypeScript + IBM Carbon 提供管理台、Prompt 管理和语音测试台。

## 4. 当前代码基线

| 领域 | 当前实现 |
| --- | --- |
| 后端 | FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL, Redis 配置预留 |
| 前端 | React 18, TypeScript, Vite, IBM Carbon, React Query, i18next |
| 语音/LLM | Gemini Live 浏览器直连已可用于验证模型能力；Twilio Media Streams 自建桥接是产品主链路但多轮稳定性仍是 P0；Twilio 官方 Conversational Agents 仅作为对照/fallback 链路 |
| 数据 | calls, appointments, prompt_templates 三类核心表 |
| 测试 | 后端服务/API 测试与前端 Vitest 单测已存在，仓库内当前约 110 个 test 文件 |
| 运行方式 | 本地 Docker Compose 启动 PostgreSQL/Redis，后端 Poetry，前端 npm/Vite |

## 5. 关联专项文档

交接时建议同时参考以下已有文档：

- [系统架构](../ARCHITECTURE.md)
- [Twilio + Gemini 语音架构](../TWILIO_GEMINI_VOICE_ARCHITECTURE.md)
- [语音网关链路说明](../../backend/docs/VOICE_GATEWAYS.md)
- [后端 API 指南](../../backend/docs/API_GUIDE.md)
- [后端配置说明](../../backend/docs/CONFIG.md)
- [数据库指南](../../backend/docs/DATABASE.md)
- [前端 API 契约](../FRONTEND_API_CONTRACT.md)
- [前端项目结构](../../frontend/docs/PROJECT_STRUCTURE.md)

## 6. 交接原则

1. 当前最高优先级是稳定 `Twilio 电话入口 -> 自建 Media Streams -> Gemini Live -> Twilio 播放` 多轮主链路，上云工作必须排在它之后。
2. 语音问题先按链路分层定位：浏览器直连验证 Gemini 能力，官方 CX 作为对照组，自建 Media Streams 作为产品主路径。
3. 预约落库规则只维护在业务服务层，不下沉到 Twilio 或 WebSocket endpoint。
4. PromptTemplate 是运行时配置，不是确定性业务状态机。
5. WebSocket 音频循环内禁止阻塞 I/O；任何耗时处理都应异步化或转移到边界外。
