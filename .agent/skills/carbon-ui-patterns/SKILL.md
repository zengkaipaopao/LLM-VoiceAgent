---
name: Carbon Design System 组件模式
description: IBM Carbon React 组件使用指南和最佳实践
---

# Carbon Design System 组件模式技能

## 何时使用此技能

当用户提到以下关键词时激活:
- "Carbon"
- "UI 组件"
- "前端"
- "DataTable"
- "Modal"
- "Notification"
- "Carbon Design"

## Carbon 组件库概览

本项目使用 **IBM Carbon Design System** (`@carbon/react`) 作为 UI 组件库。

### 核心优势
- 🎨 **企业级设计**: 专业、一致的视觉风格
- ♿ **无障碍**: 符合 WCAG 2.1 AA 标准
- 📱 **响应式**: 自适应各种屏幕尺寸
- 🌍 **国际化**: 内置多语言支持

## 常用组件模式

### 1. DataTable - 数据表格

**基础用法**:
```typescript
import {
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
} from '@carbon/react';

const headers = [
  { key: 'id', header: 'ID' },
  { key: 'name', header: '姓名' },
  { key: 'status', header: '状态' },
];

const rows = [
  { id: '1', name: 'Alice', status: 'active' },
  { id: '2', name: 'Bob', status: 'inactive' },
];

<DataTable rows={rows} headers={headers}>
  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
    <Table {...getTableProps()}>
      <TableHead>
        <TableRow>
          {headers.map((header) => (
            <TableHeader {...getHeaderProps({ header })}>
              {header.header}
            </TableHeader>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow {...getRowProps({ row })}>
            {row.cells.map((cell) => (
              <TableCell key={cell.id}>{cell.value}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )}
</DataTable>
```

**高级功能**:
- 排序: 添加 `isSortable` 到 header
- 过滤: 使用 `TableToolbar` 和 `TableToolbarSearch`
- 分页: 使用 `Pagination` 组件
- 行选择: 添加 `radio` 或 `checkbox` 到 DataTable props

### 2. Modal - 模态对话框

```typescript
import { Modal } from '@carbon/react';

const [open, setOpen] = useState(false);

<Modal
  open={open}
  onRequestClose={() => setOpen(false)}
  modalHeading="确认删除"
  primaryButtonText="删除"
  secondaryButtonText="取消"
  danger
  onRequestSubmit={handleDelete}
>
  <p>确定要删除这条记录吗?此操作无法撤销。</p>
</Modal>
```

### 3. Notification - 通知提示

```typescript
import { ToastNotification } from '@carbon/react';

<ToastNotification
  kind="success"
  title="操作成功"
  subtitle="通话记录已创建"
  timeout={3000}
  onClose={() => {}}
/>
```

**通知类型**:
- `success`: 成功操作
- `error`: 错误提示
- `warning`: 警告信息
- `info`: 一般信息

### 4. Form - 表单组件

```typescript
import { Form, TextInput, Select, SelectItem, Button } from '@carbon/react';

<Form onSubmit={handleSubmit}>
  <TextInput
    id="caller-number"
    labelText="主叫号码"
    placeholder="+8613800138000"
    required
  />
  
  <Select
    id="status"
    labelText="状态"
    defaultValue="active"
  >
    <SelectItem value="active" text="活跃" />
    <SelectItem value="completed" text="已完成" />
  </Select>
  
  <Button type="submit">提交</Button>
</Form>
```

### 5. Loading - 加载状态

```typescript
import { Loading, InlineLoading } from '@carbon/react';

// 全屏加载
<Loading active={isLoading} description="加载中..." />

// 内联加载
<InlineLoading
  status={isLoading ? 'active' : 'finished'}
  description="保存中..."
/>
```

## 主题定制

### 1. 使用内置主题

```typescript
import { Theme } from '@carbon/react';

<Theme theme="g10">  {/* 白色主题 */}
  <App />
</Theme>

<Theme theme="g100">  {/* 深色主题 */}
  <App />
</Theme>
```

### 2. 自定义 CSS 变量

```css
:root {
  --cds-interactive-01: #0f62fe;  /* 主色调 */
  --cds-interactive-02: #393939;  /* 次要色 */
  --cds-ui-background: #ffffff;   /* 背景色 */
}
```

## 响应式布局

### Grid 系统

```typescript
import { Grid, Column } from '@carbon/react';

<Grid>
  <Column sm={4} md={8} lg={16}>
    {/* 小屏 4 列, 中屏 8 列, 大屏 16 列 */}
  </Column>
</Grid>
```

### 断点

- `sm`: 320px - 671px (手机)
- `md`: 672px - 1055px (平板)
- `lg`: 1056px - 1311px (桌面)
- `xlg`: 1312px - 1583px (大屏)
- `max`: 1584px+ (超大屏)

## 图标使用

```typescript
import { Add, TrashCan, Edit } from '@carbon/icons-react';

<Button renderIcon={Add}>添加</Button>
<Button kind="danger" renderIcon={TrashCan}>删除</Button>
<Button kind="ghost" renderIcon={Edit}>编辑</Button>
```

## 最佳实践

### 1. 使用 Tile 组织内容

```typescript
import { Tile } from '@carbon/react';

<Tile>
  <h3>统计信息</h3>
  <p>今日通话: 156</p>
</Tile>
```

### 2. 使用 Stack 布局

```typescript
import { Stack } from '@carbon/react';

<Stack gap={6}>
  <div>项目 1</div>
  <div>项目 2</div>
  <div>项目 3</div>
</Stack>
```

### 3. 无障碍标签

```typescript
<Button
  aria-label="删除通话记录"
  hasIconOnly
  renderIcon={TrashCan}
/>
```

## 参考资源

- Carbon 官方文档: https://carbondesignsystem.com/
- 组件示例: https://react.carbondesignsystem.com/
- 项目中的使用: `frontend/src/components/`
