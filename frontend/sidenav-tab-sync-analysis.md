# SideNav与TestPage Tab不同步问题分析

## 问题根源

你的代码中存在**两个独立的Tab配置**，它们没有保持同步：

### 1. SideNav配置 (`src/config/navigation.ts`)
```ts
export const testNavItems = [
  { tab: 'call-simulation', label: 'simulation' },
  { tab: 'reviewer', label: 'reviewer' },
  { tab: 'websocket', label: 'websocket' },
  { tab: 'twilio', label: 'twilio' },
];
```
**缺少:** `appointment` tab

### 2. TestPage配置 (`src/pages/TestPage.tsx`)
```ts
const tabMap = ['call-simulation', 'reviewer', 'websocket', 'twilio'];
```
**同样缺少:** `appointment` tab

### 3. TestPage的实际Tab
但在TestPage的UI中，你实际渲染了5个Tab：
```tsx
<Tab>Call Simulation</Tab>    // call-simulation
<Tab>Appointment</Tab>          // appointment ⚠️ 存在但没在配置中
<Tab>Reviewer</Tab>             // reviewer
<Tab>WebSocket</Tab>            // websocket
<Tab>Twilio</Tab>               // twilio
```

## 问题表现

1. **SideNav中看不到"预约模拟"** - 因为 `testNavItems` 没有 `appointment`
2. **点击页面Appointment tab无法通过SideNav导航** - 因为 `tabMap` 和 `testNavItems` 不匹配
3. **标签名字不一样** - 两个地方使用不同的翻译key

---

## 修复方案

需要让三个地方保持一致：
1. `navigation.ts` 的 `testNavItems`
2. `TestPage.tsx` 的 `tabMap`
3. `TestPage.tsx` 的实际 Tab UI

### 修复步骤：

#### 1. 更新 `navigation.ts`
添加 `appointment` 到 `testNavItems`：
```ts
export const testNavItems = [
  { tab: 'call-simulation', label: 'simulation' },
  { tab: 'appointment', label: 'appointment' },  // 新增
  { tab: 'reviewer', label: 'reviewer' },
  { tab: 'websocket', label: 'websocket' },
  { tab: 'twilio', label: 'twilio' },
];
```

#### 2. 更新 `TestPage.tsx` 的 tabMap
```ts
const tabMap = ['call-simulation', 'appointment', 'reviewer', 'websocket', 'twilio'];
```

#### 3. 调整TestPage的Tab顺序（与tabMap一致）
确保UI中的Tab顺序与 `tabMap` 数组顺序完全一致。

---

## 最佳实践建议

**推荐：单一数据源 (Single Source of Truth)**

将Tab配置统一管理，避免重复定义：

```ts
// src/config/navigation.ts
export const testTabs = [
  { id: 'call-simulation', label: 'simulation', icon: Phone },
  { id: 'appointment', label: 'appointment', icon: User },
  { id: 'reviewer', label: 'reviewer', icon: WatsonHealthAiStatus },
  { id: 'websocket', label: 'websocket', icon: Network_3 },
  { id: 'twilio', label: 'twilio', icon: PhoneVoice },
];
```

然后在TestPage中直接使用这个配置动态生成Tab，避免手动维护同步。
