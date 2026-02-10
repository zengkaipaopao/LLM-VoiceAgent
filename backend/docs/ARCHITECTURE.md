# 后端架构设计文档 (Backend Architecture)

> **📖 延伸阅读**: 本文档聚焦后端分层架构设计。如需了解完整的系统架构（包括前后端、基础设施等），请参考 [项目架构总览](../../docs/ARCHITECTURE.md)。

## 1. 核心设计理念 (Core Philosophy)

本项目采用 **分层架构 (Layered Architecture)** 设计，旨在实现高内聚、低耦合的企业级微服务。目前阶段专注于 **Simulation (模拟)** 能力，但架构本身已为未来接入真实业务（如真实的电话线路、LLM 推理）做好了准备。

### 关键原则
- **关注点分离 (Separation of Concerns)**: API 层只负责接收请求，Service 层处理业务逻辑，Repository 层负责数据读写。
- **依赖倒置 (Dependency Injection)**: 通过 FastAPI 的 `Depends` 注入数据库会话和依赖项，便于测试和维护。
- **数据契约 (Data Contracts)**: 使用 Pydantic (`schemas`) 严格定义前后端交互的数据格式，确保接口稳定。
- **扁平化接口 (Flat API Style)**: 遵循 RESTful 最佳实践，移除冗余的 Envelope 包装，降低前端对接成本。

---

## 2. 文件夹结构说明 (Folder Structure)

```
backend/app/
├── api/                  # [接口层] The "Front Desk"
│   ├── v1/endpoints/     # 具体业务接口 (如 /appointments, /calls)
│   └── deps.py           # 依赖注入 (如 get_db)
│
├── core/                 # [核心层] The "Engine Room"
│   ├── config.py         # 全局配置 (环境变量管理)
│   └── database.py       # 数据库连接池
│
├── models/               # [数据层 - 实体] The "Tables"
│   ├── appointment.py    # 定义数据库表结构 (SQLAlchemy)
│   └── call.py
│
├── schemas/              # [契约层] The "Contracts"
│   ├── appointments.py   # 定义 API 请求/响应的数据格式 (Pydantic)
│   └── call.py
│
├── repositories/         # [仓储层] The "Warehouse"
│   ├── base_repository.py # 通用 CRUD 封装
│   └── appointment_repository.py # 具体的数据库查询逻辑
│
└── services/             # [业务层] The "Brain"
    ├── appointment_simulation_service.py # 复杂的业务逻辑 (如生成模拟数据)
    └── call_simulation_service.py
```

---

## 3. 数据流向 (Data Flow)

一个典型的请求处理流程如下：

1.  **Request**: 用户发起请求 (e.g., POST `/api/v1/appointments/simulate`)。
2.  **API Layer** (`api/`): 路由接收请求，验证参数格式 (`schemas`)。
3.  **Service Layer** (`services/`): 调用业务逻辑 (e.g., 生成随机预约数据，处理状态流转)。
4.  **Repository Layer** (`repositories/`): 执行数据库操作 (INSERT/UPDATE)。
5.  **Database** (`models/`): 数据持久化到 PostgreSQL。
6.  **Response**: 数据经由 `schemas` 序列化为 JSON 返回给用户。

---

## 4. 最终形态展望 (The Final Vision)

随着项目演进，这个后端将成为一个标准的 **云原生微服务 (Cloud-Native Microservice)**：

- **容器化 (Containerized)**: 通过 Docker 进行标准化交付，支持 K8s 部署。
- **无状态 (Stateless)**: 应用本身不存储状态（状态在 DB/Redis），支持水平扩展 (Horizontal Scaling)。
- **可观测 (Observable)**: 未来可接入 Prometheus/Grafana 进行监控。
- **迁移管理 (Migration Managed)**: 所有的数据库变更都通过 Alembic 版本化管理，杜绝手动修改生产库。

目前我们已经完成了上述大部分基础建设（Docker, Alembic, Clean Architecture），基础非常牢固。
