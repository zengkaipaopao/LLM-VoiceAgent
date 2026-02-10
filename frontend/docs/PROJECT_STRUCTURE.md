# 前端项目结构说明

## 📁 目录结构

```
src/
├── components/       # UI组件(原子化设计)
│   ├── atoms/       # 原子组件
│   ├── molecules/   # 分子组件
│   ├── organisms/   # 有机体组件
│   └── templates/   # 模板组件
│
├── pages/           # 页面组件
│   ├── DashboardPage.tsx
│   ├── CallsPage.tsx
│   ├── AppointmentsPage.tsx
│   ├── PromptsPage.tsx
│   ├── SettingsPage.tsx
│   └── PretrainingPage.tsx
│
├── features/        # 功能模块(自包含)
│   └── test/       # 测试控制台功能
│       ├── components/
│       ├── hooks/
│       └── utils/
│
├── hooks/           # 全局自定义Hooks
│   ├── useDebounce.ts
│   └── index.ts
│
├── api/             # API客户端
│   ├── calls.ts
│   ├── appointments.ts
│   └── prompts.ts
│
├── types/           # TypeScript类型定义
│   ├── index.ts
│   └── css.d.ts
│
├── config/          # 配置文件
│   ├── i18n.ts     # 国际化配置
│   └── navigation.ts
│
├── utils/           # 工具函数
│   ├── formatters.ts
│   ├── validators.ts
│   └── index.ts
│
├── App.tsx          # 根组件
├── main.tsx         # 应用入口
└── styles.css       # 全局样式
```
│       ├── components/
│       ├── hooks/
│       └── utils/
│
├── hooks/           # 全局自定义Hooks
│   └── (业务相关的Hooks)
│
├── api/             # API客户端
│   ├── calls.ts
│   ├── appointments.ts
│   └── prompts.ts
│
├── types/           # TypeScript类型定义
│   └── index.ts
│
├── config/          # 配置文件
│   ├── i18n.ts     # 国际化配置
│   └── navigation.ts
│
├── utils/           # 工具函数
│   └── (通用工具函数)
│
├── styles/          # 样式文件
│   └── styles.css
│
├── App.tsx          # 根组件
└── main.tsx         # 应用入口
```

## 📝 文件夹说明

### components/
存放可复用的UI组件,按照原子化设计组织:
- **atoms/**: 最小UI单元(按钮、标题)
- **molecules/**: 简单组合(搜索栏、语言切换器)
- **organisms/**: 复杂功能(页面头部、空状态)
- **templates/**: 页面布局(通用页面模板)

### pages/
存放页面级组件,每个页面对应一个路由。

### features/
存放功能模块,每个功能模块自包含所需的组件、Hooks和工具。

### hooks/
存放全局自定义Hooks,包含业务逻辑的可复用逻辑。

**示例**:
- `useCallsList.ts` - 获取通话列表
- `useAuth.ts` - 认证相关逻辑
- `useDebounce.ts` - 防抖Hook

### api/
存放API客户端代码,每个资源一个文件。

### types/
存放TypeScript类型定义。

### config/
存放配置文件,如国际化配置、导航配置等。

### utils/
存放工具函数,纯函数,无副作用。

**示例**:
- `formatters.ts` - 格式化函数
- `validators.ts` - 验证函数

## 🎯 组织原则

### 1. 就近原则
代码应该放在离使用它的地方最近的位置。

### 2. 单一职责
每个文件夹只负责一类内容。

### 3. 自包含
功能模块(features)应该包含该功能所需的所有代码。

### 4. 扁平化
避免过深的嵌套,最多3层。

## 📋 文件命名规范

### 组件文件
- 格式: `ComponentName.tsx`
- 示例: `PageHeader.tsx`, `EmptyState.tsx`

### Hooks文件
- 格式: `use + 功能名 + .ts`
- 示例: `useCallsList.ts`, `useDebounce.ts`

### 工具文件
- 格式: `功能名 + s.ts` (复数)
- 示例: `formatters.ts`, `validators.ts`

### API文件
- 格式: `资源名 + .ts`
- 示例: `calls.ts`, `appointments.ts`

## 🔍 如何决定文件放在哪里?

```
这段代码是...
    │
    ├─ UI组件? → components/
    │
    ├─ 页面? → pages/
    │
    ├─ 自定义Hook? → hooks/
    │
    ├─ 工具函数? → utils/
    │
    ├─ API调用? → api/
    │
    ├─ 类型定义? → types/
    │
    ├─ 配置? → config/
    │
    └─ 功能模块特定? → features/[功能名]/
```

## ✅ 最佳实践

1. **保持简单** - 不确定就放在最简单的位置
2. **避免重复** - 同类文件放在同一个文件夹
3. **及时重构** - 发现不合理及时调整
4. **团队一致** - 遵循统一的规范

## 🚫 已删除的文件夹

- ~~`shared/`~~ - 单项目不需要
- ~~`state/`~~ - 使用Context API或React Query代替

## 📚 参考

详细说明请查看:
- [前端开发指南](../docs/FRONTEND_DEVELOPMENT_GUIDE.md)
- [原子化设计文档](./ATOMIC_DESIGN.md)
