# LLM Voice Agent Architecture

## Overview
The project provides a modular platform for inbound and outbound telephony experiences that are orchestrated by large language models (LLMs). It is split into a React + TypeScript dashboard and a Python service layer. Both surfaces communicate through a well-defined REST API, making it straightforward to swap providers or scale components independently.

### Deployment mode
- 当前阶段采用**模块化单体**：FastAPI 应用内部通过 `core/services/repositories` 分层完成解耦，并暴露 `/api` 接口供 React dashboard 调用。
- 需要异步解耦时，可先引入消息队列/任务队列中间件，把 telephony webhook、LLM 推理流程异步化，而不是立即拆成多个微服务。
- 随着并发和团队规模增长，可以把 `telephony`、`llm-orchestrator`、`analytics` 等模块提取为独立服务；由于代码组织已经遵循依赖倒置，迁移时不必大拆大改。

```
frontend (React + Vite)
├─ src/
│  ├─ pages/
│  ├─ components/
│  ├─ state/
│  ├─ api/
│  └─ types/
└─ tests/

backend (FastAPI)
├─ app/
│  ├─ api/v1/        # 路由层，聚合 REST 接口
│  ├─ services/      # 领域逻辑 (call flow, telephony, llm, prompts)
│  ├─ repositories/  # 数据访问与持久化抽象
│  ├─ schemas/       # Pydantic 模型
│  └─ core/          # 配置、启动依赖
└─ tests/
```

## Key Concepts
- **Telephony adapters** encapsulate integrations for placing/receiving calls (e.g., Twilio, SIP). They expose a consistent interface consumed by the call flow service.
- **LLM orchestration** defines prompt templates, session memory, and tool usage. The interface makes it trivial to switch between providers or models.
- **Call flows** coordinate telephony events, persistence, and LLM prompts. They log every interaction for later review in the dashboard.
- **Dashboard** surfaces call history, prompt configurations, agent status, and webhook health checks。UI 采用 IBM Carbon Design System（`@carbon/react` + UIShell），保证企业级一致性。
- **Persistence** uses a repository pattern. By default it ships with an in-memory store but can be swapped for Postgres or any ORM implementation without touching business logic.

## Data Model Snapshot
- `CallLog`: metadata about the call, caller/callee info, timestamps, transcript summary, status, cost metrics.
- `PromptTemplate`: name, system prompt, sample responses, version history.
- `AgentProfile`: runtime configuration for inbound/outbound agents (LLM provider, voice, telemetry flags).

## API Surface (initial)
- `GET /health` — readiness/liveness for probes.
- `GET /calls` — list paginated call logs.
- `POST /calls/outbound` — kick off a proactive call with prompt + callee metadata.
- `POST /webhooks/telephony` — receives webhook callbacks (answer, hangup, speech events).
- `GET/PUT /prompts` — browse and edit prompt templates.

## Extensibility Hooks
- `TelephonyAdapter` abstract class for vendor-specific behavior.
- `LLMClient` interface to connect to OpenAI, Anthropic, Azure OpenAI, etc.
- Plug-in style registry for analytics/speech features in `services/call_flow.py`.
- Frontend environment-driven feature flags for staging/beta modules.

Refer to the README for setup instructions.
