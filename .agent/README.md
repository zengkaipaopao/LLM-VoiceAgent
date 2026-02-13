# .agent 目录说明

本目录包含 AI 辅助开发的配置文件,用于引导 Google Antigravity 等 AI 工具更好地理解和辅助项目开发。

## 目录结构

```
.agent/
├── rules/              # 规则 - 始终生效的系统级指令
│   ├── llm.md         # 核心技术栈和架构规则
│   ├── code-style-guide.md
│   ├── architecture-patterns.md
│   ├── testing-standards.md
│   └── api-design-guide.md
├── workflows/          # 工作流 - 可按需触发的任务
│   ├── run-backend-tests.md
│   ├── run-frontend-tests.md
│   ├── generate-api-docs.md
│   ├── database-migration.md
│   ├── deploy-staging.md
│   └── code-review-checklist.md
├── skills/             # 技能 - 专业知识包,按需激活
│   ├── websocket-debugging/
│   ├── async-performance/
│   └── carbon-ui-patterns/
└── README.md          # 本文件
```

## 三大组件说明

### 1. Rules (规则)

**用途**: 系统级指令,始终生效,引导 AI 的代码生成和决策行为

**何时使用**: 
- 定义代码风格规范
- 强制执行架构模式
- 设定测试标准
- 统一 API 设计

**示例**:
- `code-style-guide.md`: Python PEP 8 和 TypeScript Prettier 规范
- `architecture-patterns.md`: Repository、Adapter、依赖注入模式

**特点**:
- 自动应用于所有对话
- 通过 YAML frontmatter `trigger: always_on` 激活

### 2. Workflows (工作流)

**用途**: 可通过 `/` 命令按需触发的保存提示,用于常见任务

**何时使用**:
- 运行测试
- 生成文档
- 数据库迁移
- 部署流程
- 代码审查

**如何触发**:
在 AI 对话中输入 `/` 后跟工作流名称,例如:
- `/run-backend-tests` - 运行后端测试
- `/generate-api-docs` - 生成 API 文档
- `/code-review-checklist` - 显示代码审查清单

**特点**:
- 按需触发,不占用上下文
- 可包含 `// turbo` 注释自动执行命令

### 3. Skills (技能)

**用途**: 专业知识包,仅在相关场景下激活,避免上下文膨胀

**何时使用**:
- 提供特定领域的深度知识
- 包含脚本、工具或参考文档
- 针对项目特定的技术栈

**如何激活**:
当对话中提到技能描述中的关键词时自动激活,例如:
- 提到 "WebSocket" → 激活 `websocket-debugging` 技能
- 提到 "性能优化" → 激活 `async-performance` 技能
- 提到 "Carbon" → 激活 `carbon-ui-patterns` 技能

**技能结构**:
```
skill-name/
├── SKILL.md           # 必需: 技能说明和指令
├── scripts/           # 可选: 辅助脚本
├── references/        # 可选: 参考文档
└── assets/            # 可选: 图片或资源
```

## 如何添加自定义配置

### 添加新规则

1. 在 `.agent/rules/` 创建新的 `.md` 文件
2. 添加 YAML frontmatter:
   ```yaml
   ---
   trigger: always_on
   ---
   ```
3. 编写规则内容

### 添加新工作流

1. 在 `.agent/workflows/` 创建新的 `.md` 文件
2. 添加 YAML frontmatter:
   ```yaml
   ---
   description: 工作流简短描述
   ---
   ```
3. 编写步骤说明
4. 使用 `// turbo` 注释标记可自动执行的命令

### 添加新技能

1. 在 `.agent/skills/` 创建新目录
2. 创建 `SKILL.md` 文件,包含:
   ```yaml
   ---
   name: 技能名称
   description: 技能描述
   ---
   ```
3. 说明激活条件(关键词)
4. 添加使用指南和示例
5. (可选) 添加 `scripts/`、`references/` 等子目录

## 常用工作流列表

| 命令 | 功能 |
|------|------|
| `/run-backend-tests` | 运行后端单元测试和集成测试 |
| `/run-frontend-tests` | 运行前端测试套件 |
| `/generate-api-docs` | 生成 OpenAPI 文档 |
| `/database-migration` | 创建和应用数据库迁移 |
| `/deploy-staging` | 部署到测试环境 |
| `/code-review-checklist` | 显示代码审查清单 |

## 最佳实践

1. **规则要简洁**: 规则会占用上下文,保持简洁明了
2. **工作流要具体**: 提供明确的步骤和命令
3. **技能要聚焦**: 每个技能专注于一个特定领域
4. **持续更新**: 随着项目演进更新配置

## 参考资源

- Google Antigravity 指南: https://codelabs.developers.google.com/getting-started-google-antigravity
- 项目架构文档: [../docs/ARCHITECTURE.md](file:///Users/zeng/Desktop/LLM-VoiceAgent/docs/ARCHITECTURE.md)
