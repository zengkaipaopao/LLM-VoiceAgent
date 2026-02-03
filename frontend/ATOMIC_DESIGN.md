# 原子化设计架构文档

本文档说明了项目采用的原子化设计(Atomic Design)模式和Carbon Design System集成方案。

## 什么是原子化设计?

原子化设计是由Brad Frost提出的一种设计方法论,将UI组件按照复杂度分为五个层次:

```
Atoms (原子) → Molecules (分子) → Organisms (有机体) → Templates (模板) → Pages (页面)
```

这种层次化的组织方式使得组件更加模块化、可复用和易于维护。

## 项目目录结构

```
src/
├── components/
│   ├── atoms/          # 原子组件 - 最基础的UI元素
│   │   ├── PageTitle.tsx
│   │   └── PageSubtitle.tsx
│   ├── molecules/      # 分子组件 - 由多个原子组合而成
│   │   └── (待扩展)
│   ├── organisms/      # 有机体组件 - 复杂的功能模块
│   │   ├── PageHeader.tsx
│   │   └── EmptyState.tsx
│   └── templates/      # 模板组件 - 页面级布局
│       └── PageTemplate.tsx
├── pages/              # 页面组件 - 具体的业务页面
│   ├── DashboardPage.tsx
│   ├── CallsPage.tsx
│   ├── AppointmentsPage.tsx
│   ├── PromptsPage.tsx
│   ├── SettingsPage.tsx
│   └── PretrainingPage.tsx
└── config/
    └── theme.ts        # Carbon Design System 主题配置
```

## 组件层次说明

### 1. Atoms (原子)

**定义**: 最基础的UI元素,不可再分割的组件。

**特点**:
- 单一职责,功能明确
- 高度可复用
- 无业务逻辑
- 通常是对Carbon组件的简单封装

**示例**:
- `PageTitle` - 页面标题
- `PageSubtitle` - 页面副标题
- `Button` - 按钮
- `Input` - 输入框
- `Label` - 标签

**使用场景**: 作为构建更复杂组件的基础单元。

### 2. Molecules (分子)

**定义**: 由多个原子组件组合而成的简单组件。

**特点**:
- 组合2-3个原子组件
- 实现简单的交互逻辑
- 可独立使用
- 保持简洁

**示例**:
- `SearchBar` - 搜索栏 (Input + Icon)
- `FormField` - 表单字段 (Label + Input + ErrorMessage)
- `StatCard` - 统计卡片 (Label + Value + Tag)

**使用场景**: 实现常见的UI模式,如表单输入、搜索框等。

### 3. Organisms (有机体)

**定义**: 由分子和原子组件组成的复杂组件,形成界面的独立区域。

**特点**:
- 功能相对完整
- 可包含业务逻辑
- 可独立使用或组合使用
- 通常对应一个功能模块

**示例**:
- `PageHeader` - 页面头部 (Title + Subtitle + Actions)
- `EmptyState` - 空状态展示
- `DataTable` - 数据表格
- `StatsGrid` - 统计网格

**使用场景**: 构建页面的主要功能区块。

### 4. Templates (模板)

**定义**: 定义页面布局结构的组件,组合多个有机体组件。

**特点**:
- 定义页面骨架
- 关注布局而非内容
- 提供插槽(slots)供页面填充
- 确保页面一致性

**示例**:
- `PageTemplate` - 通用页面模板
- `DashboardTemplate` - 仪表盘模板
- `ListPageTemplate` - 列表页模板

**使用场景**: 为不同类型的页面提供统一的布局框架。

### 5. Pages (页面)

**定义**: 具体的业务页面,使用模板并填充实际内容。

**特点**:
- 包含具体业务逻辑
- 使用模板组件
- 连接数据源(API、状态管理)
- 处理路由和导航

**示例**:
- `DashboardPage` - 仪表盘页面
- `CallsPage` - 通话记录页面
- `SettingsPage` - 设置页面

**使用场景**: 应用的实际页面,用户直接访问的路由。

## Carbon Design System 集成

### 主题配置

项目使用Carbon Design System的设计令牌(Design Tokens),配置文件位于 `src/config/theme.ts`。

**主要配置项**:
- **颜色系统**: 使用Carbon的颜色变量
- **间距系统**: 基于8px的间距单位
- **字体系统**: IBM Plex Sans字体家族
- **断点系统**: 响应式设计断点
- **阴影和圆角**: 统一的视觉效果

### CSS变量

所有样式使用Carbon的CSS变量,确保主题一致性:

```css
/* 颜色 */
var(--cds-text-primary, #161616)
var(--cds-text-secondary, #525252)
var(--cds-ui-background, #f4f4f4)

/* 间距 */
0.5rem  /* 8px */
1rem    /* 16px */
1.5rem  /* 24px */
```

## 组件开发指南

### 创建新组件的步骤

1. **确定组件层次**
   - 问自己: 这个组件应该属于哪个层次?
   - 原则: 从最简单的层次开始,逐步组合

2. **创建组件文件**
   ```bash
   # 原子组件
   src/components/atoms/ComponentName.tsx
   
   # 分子组件
   src/components/molecules/ComponentName.tsx
   
   # 有机体组件
   src/components/organisms/ComponentName.tsx
   ```

3. **编写组件代码**
   ```tsx
   import { ReactNode } from 'react';
   
   interface ComponentNameProps {
     children?: ReactNode;
     className?: string;
     // 其他props
   }
   
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
   ```

4. **添加样式**
   - 优先使用Carbon组件的内置样式
   - 必要时在 `styles.css` 中添加自定义样式
   - 使用Carbon的CSS变量

5. **编写文档注释**
   - 说明组件用途
   - 列出主要props
   - 提供使用示例

### 组件设计原则

1. **单一职责**: 每个组件只做一件事
2. **可组合性**: 组件应该易于组合使用
3. **可复用性**: 避免硬编码,使用props传递配置
4. **一致性**: 遵循Carbon Design规范
5. **可访问性**: 使用语义化HTML和ARIA属性

### 命名规范

- **组件文件**: PascalCase,如 `PageHeader.tsx`
- **组件函数**: PascalCase,如 `function PageHeader()`
- **Props接口**: 组件名 + Props,如 `PageHeaderProps`
- **CSS类名**: kebab-case,如 `page-header`

## 最佳实践

### 1. 优先使用Carbon组件

```tsx
// ✅ 好的做法
import { Button, Tile } from '@carbon/react';

// ❌ 避免
// 自己实现已有的Carbon组件
```

### 2. 保持组件简洁

```tsx
// ✅ 好的做法 - 简单的原子组件
export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="page-title">{children}</h1>;
}

// ❌ 避免 - 原子组件包含复杂逻辑
export function PageTitle({ children, fetchData, ... }) {
  // 大量业务逻辑...
}
```

### 3. 使用TypeScript类型

```tsx
// ✅ 好的做法
interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

// ❌ 避免
function PageHeader(props: any) { ... }
```

### 4. 提供合理的默认值

```tsx
// ✅ 好的做法
export function EmptyState({ 
  title = '暂无内容',
  description = '此页面正在开发中'
}: EmptyStateProps) { ... }
```

## 迁移现有组件

如果需要将现有组件迁移到原子化设计结构:

1. **分析组件**: 确定组件应属于哪个层次
2. **拆分组件**: 将复杂组件拆分为更小的单元
3. **移动文件**: 将组件移动到对应的目录
4. **更新导入**: 更新所有引用该组件的地方
5. **测试验证**: 确保功能正常

## 参考资源

- [Atomic Design by Brad Frost](https://atomicdesign.bradfrost.com/)
- [Carbon Design System](https://carbondesignsystem.com/)
- [Carbon React Components](https://react.carbondesignsystem.com/)
- [Carbon Design Tokens](https://carbondesignsystem.com/guidelines/color/overview)

## 总结

原子化设计帮助我们:
- ✅ 构建可复用的组件库
- ✅ 保持UI的一致性
- ✅ 提高开发效率
- ✅ 简化维护工作
- ✅ 促进团队协作

遵循这些原则,我们可以构建出结构清晰、易于维护的前端应用。
