# 前端开发指南

**版本**: 3.0  
**最后更新**: 2026-02-10  
**技术栈**: React + TypeScript + Vite + Carbon Design System

---

## 📋 目录

1. [快速开始](#快速开始)
2. [核心原则](#核心原则)
3. [项目结构](#项目结构)
4. [原子化设计](#原子化设计)
5. [开发规范](#开发规范)
6. [状态管理](#状态管理)
7. [国际化(i18n)](#国际化i18n)
8. [性能优化](#性能优化)
9. [最佳实践](#最佳实践)

---

## 快速开始

### 环境要求
- Node.js 18+
- npm 9+

### 安装和运行
```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

---

## 核心原则

### 1. 可读性优先
- 清晰的命名
- 简洁的组件
- 完善的注释
- 统一的风格

### 2. 可维护性
- 模块化设计
- 单一职责
- 低耦合高内聚
- 易于测试

### 3. 性能优化
- 按需加载
- 缓存策略
- 避免重渲染
- 优化资源

### 4. 用户体验
- 快速响应
- 友好提示
- 无障碍支持
- 国际化

---

## 项目结构

详细的项目结构说明请参考 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)。

### 目录概览
```
src/
├── components/       # UI组件(原子化设计)
│   ├── atoms/       # 原子组件
│   ├── molecules/   # 分子组件
│   ├── organisms/   # 有机体组件
│   └── templates/   # 模板组件
├── pages/           # 页面组件
├── features/        # 功能模块(自包含)
├── hooks/           # 自定义Hooks
├── api/             # API客户端
├── types/           # TypeScript类型
├── config/          # 配置文件
└── utils/           # 工具函数
```

---

## 原子化设计

本项目采用 **原子化设计(Atomic Design)** 模式组织 UI 组件。

详细说明请参考 [ATOMIC_DESIGN.md](./ATOMIC_DESIGN.md)。

### 设计层级
```
Atoms (原子) → Molecules (分子) → Organisms (有机体) → Templates (模板) → Pages (页面)
```

### 快速参考

**Atoms (原子组件)**
- 最小UI单元，不可再分
- 示例：PageTitle, PageSubtitle, Button
- 无业务逻辑，高度复用

**Molecules (分子组件)**
- 2-3个原子组合
- 示例：SearchBar, LanguageSwitcher
- 简单交互，独立使用

**Organisms (有机体组件)**
- 复杂功能模块
- 示例：PageHeader, DataTable
- 包含业务逻辑，功能完整

**Templates (模板组件)**
- 页面布局结构
- 示例：PageTemplate
- 关注布局，提供插槽

**Pages (页面组件)**
- 完整业务页面
- 示例：DashboardPage, CallsPage
- 组合模板，连接数据

---

## 开发规范

### TypeScript 使用

**类型定义**
```tsx
// ✅ 好的做法
interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  // ...
}

// ❌ 避免
function PageHeader(props: any) { ... }
```

### 命名规范

- **组件文件**: PascalCase，如 `PageHeader.tsx`
- **组件函数**: PascalCase，如 `function PageHeader()`
- **Props接口**: 组件名 + Props，如 `PageHeaderProps`
- **Hooks**: camelCase，以use开头，如 `useCallsList`
- **常量**: UPPER_SNAKE_CASE，如 `API_BASE_URL`
- **变量/函数**: camelCase，如 `userName`, `fetchData`

### 文件组织

```tsx
// 推荐的组件文件结构
import { ReactNode } from 'react';
import { Button } from '@carbon/react';
import './ComponentName.css';

// 1. 类型定义
interface ComponentNameProps {
  children?: ReactNode;
  className?: string;
}

// 2. 组件函数
/**
 * ComponentName - 组件简短描述
 * 
 * 详细说明组件的用途和使用场景
 */
export function ComponentName({ 
  children, 
  className = '',
  ...props 
}: ComponentNameProps) {
  return (
    <div className={`component-name ${className}`.trim()}>
      {children}
    </div>
  );
}

// 3. 默认导出(可选)
export default ComponentName;
```

---

## 状态管理

### 状态分类

**本地状态 (useState)**
- 用途：组件内部状态
- 示例：表单输入、开关状态

**服务端状态 (React Query)**
- 用途：API数据管理
- 示例：通话列表、用户信息
- 优势：自动缓存、重试、更新

**全局状态 (Context)**
- 用途：跨组件共享
- 示例：主题、语言、用户信息

**URL状态 (路由参数)**
- 用途：可共享的状态
- 示例：搜索条件、分页

### 状态管理原则

1. **就近原则**：状态放在最近的父组件
2. **最小化**：只存储必要的状态
3. **单一数据源**：避免状态重复
4. **不可变**：使用不可变更新

---

## 国际化(i18n)

### 配置结构

```
locales/
├── zh-CN/
│   ├── common.json      # 通用文本
│   ├── pages.json       # 页面文本
│   └── navigation.json  # 导航文本
├── en-US/
└── ja-JP/
```

### 使用方法

```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation(['common', 'pages']);
  
  return (
    <div>
      <h1>{t('pages:dashboard.title')}</h1>
      <button>{t('common:buttons.save')}</button>
    </div>
  );
}
```

### 最佳实践

- ✅ 所有文本都要翻译
- ✅ 提取重复文本到 common
- ✅ 使用插值处理动态内容
- ✅ 定期检查缺失翻译
- ❌ 避免硬编码文本

---

## 性能优化

### 代码分割

```tsx
// 路由级别懒加载
import { lazy, Suspense } from 'react';

const CallsPage = lazy(() => import('./pages/CallsPage'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <CallsPage />
    </Suspense>
  );
}
```

### 渲染优化

```tsx
// 使用 React.memo
export const ExpensiveComponent = React.memo(({ data }) => {
  // ...
});

// 使用 useCallback
const handleClick = useCallback(() => {
  // ...
}, [dependency]);

// 使用 useMemo
const computedValue = useMemo(() => {
  return expensiveCalculation(data);
}, [data]);
```

---

## 最佳实践

### 开发检查清单

**代码质量**
- [ ] TypeScript无错误
- [ ] ESLint无警告
- [ ] 代码已格式化
- [ ] 无console.log

**组件设计**
- [ ] 遵循原子化设计
- [ ] Props类型完整
- [ ] 有文档注释
- [ ] 可复用性高

**性能**
- [ ] 使用React.memo
- [ ] 避免不必要渲染
- [ ] 代码已分割
- [ ] 资源已优化

**国际化**
- [ ] 无硬编码文本
- [ ] 翻译完整
- [ ] 命名空间正确

### Carbon Design System 集成

**优先使用Carbon组件**
```tsx
// ✅ 好的做法
import { Button, Tile, DataTable } from '@carbon/react';

// ❌ 避免
// 自己实现已有的Carbon组件
```

**使用Carbon设计令牌**
```css
/* 颜色 */
color: var(--cds-text-primary);
background: var(--cds-ui-background);

/* 间距 */
padding: 1rem;  /* 16px, 基于8px网格 */
margin: 0.5rem; /* 8px */

/* 字体 */
font-family: 'IBM Plex Sans', sans-serif;
```

---

## 常见问题

### 组件放在哪个层级？

问自己以下问题：
1. 这个组件可以再拆分吗？→ 如果不能，可能是原子
2. 这个组件由2-3个简单组件组成吗？→ 可能是分子
3. 这个组件是一个完整的功能模块吗？→ 可能是有机体
4. 这个组件定义页面布局吗？→ 可能是模板
5. 这个组件是完整的业务页面吗？→ 是页面

### 如何避免重复代码？

1. 提取通用组件到 components/
2. 提取通用逻辑到 hooks/
3. 提取工具函数到 utils/
4. 使用组件组合而非继承

---

## 参考资源

### 官方文档
- [React官方文档](https://react.dev/)
- [TypeScript文档](https://www.typescriptlang.org/)
- [Carbon Design System](https://carbondesignsystem.com/)
- [React Query文档](https://tanstack.com/query/latest)
- [i18next文档](https://www.i18next.com/)

### 推荐阅读
- [Atomic Design by Brad Frost](https://atomicdesign.bradfrost.com/)
- React性能优化最佳实践
- TypeScript进阶指南

---

**文档维护**: 随项目演进持续更新  
**相关文档**: [原子化设计](./ATOMIC_DESIGN.md) | [项目结构](./PROJECT_STRUCTURE.md)
