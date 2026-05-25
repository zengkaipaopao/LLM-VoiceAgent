# LLMVoiceDesk

企业级 LLM 语音座席项目的单体架构骨架，包含：

- **frontend**：React + TypeScript + Vite 仪表盘（使用 IBM Carbon Design System），展示通话、Prompt、Agent 设置。
- **backend**：FastAPI 应用，解耦的 call-flow、telephony、LLM、Prompt 管理等模块。
- **docs**：架构说明与扩展路线。

## 快速开始

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

## 设计系统
- 前端采用 [IBM Carbon React](https://carbondesignsystem.com/)。`AppLayout` 已经接入 Carbon UIShell、主题（`g10`），`Dashboard/Calls/Prompts/Settings` 等页面均使用 `Tile`、`DataTable`、`Grid` 等官方组件。
- 在 `src/main.tsx` 最顶部引入 `wicg-inert/dist/inert.esm.js` polyfill（Carbon UIShell 依赖 `inert` 属性），随后引入 `@carbon/styles/css/styles.css`；编写新组件时直接从 `@carbon/react` 引用即可，若需要图标使用 `@carbon/icons-react`。
- 若要自定义主题，可在 `AppLayout` 中调整 `<Theme theme=\"g10\">` 或通过 CSS 自定义属性覆盖局部样式。

## 📚 文档

- [系统架构](./docs/ARCHITECTURE.md) - 完整的系统架构设计
- [项目交接文档集](./docs/handover/README.md) - 需求分析、基本设计、详细设计、运维交接、当前阶段与 TODO
- [后端文档](./backend/README.md) - 后端开发文档
- [前端文档](./frontend/README.md) - 前端开发文档

## 下一步建议
1. 将 `repositories` 接入真实数据库（Postgres/Redis）并实现查询/分页。
2. 把 `telephony_adapter`、`llm_client` 接入目标供应商并在 services 中注入。
3. Dashboard 通过 React Query 调真实 API，添加表格过滤、详情侧栏、Prompt 编辑器等功能。
