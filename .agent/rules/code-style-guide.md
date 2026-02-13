---
trigger: always_on
---

# 代码风格规范

## Python 代码规范 (Backend)

### 格式化标准
- **严格遵循 PEP 8**: 所有 Python 代码必须符合 PEP 8 规范
- **使用 Black 格式化**: 最大行长 100 字符
- **导入顺序**: 
  1. 标准库
  2. 第三方库
  3. 本地应用/库
  - 每组之间空一行,使用 `isort` 自动排序

### 命名规范
- **函数/变量**: `snake_case` (例: `get_user_info`, `total_count`)
- **类名**: `PascalCase` (例: `UserRepository`, `CallService`)
- **常量**: `UPPER_SNAKE_CASE` (例: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`)
- **私有成员**: 前缀 `_` (例: `_internal_method`)
- **避免单字母变量**: 除了循环索引 `i`, `j` 或数学公式中的变量

### 类型注解
- **强制类型提示**: 所有函数参数和返回值必须有类型注解
```python
async def get_call_by_id(call_id: UUID) -> Optional[Call]:
    pass
```
- **使用 Pydantic**: 所有 API 输入/输出使用 Pydantic 模型验证
- **避免 `Any`**: 除非绝对必要,使用具体类型或 `Union`

### 文档字符串
- **所有公共函数/类必须有 docstring**
- **使用 Google 风格**:
```python
async def create_appointment(
    customer_name: str,
    phone: str,
    appointment_time: datetime
) -> Appointment:
    """创建新的预约记录.
    
    Args:
        customer_name: 客户姓名
        phone: 联系电话 (E.164 格式)
        appointment_time: 预约时间
        
    Returns:
        创建的预约对象
        
    Raises:
        ValidationError: 当输入数据不合法时
        DatabaseError: 当数据库操作失败时
    """
    pass
```

### 代码组织
- **函数长度**: 单个函数不超过 50 行,超过则拆分
- **单一职责**: 每个函数只做一件事
- **避免深层嵌套**: 最多 3 层 if/for 嵌套,使用 early return

---

## TypeScript 代码规范 (Frontend)

### 格式化标准
- **使用 Prettier**: 配置文件 `.prettierrc`
- **最大行长**: 100 字符
- **缩进**: 2 空格
- **分号**: 必须使用
- **引号**: 单引号 (JSX 中使用双引号)

### 命名规范
- **变量/函数**: `camelCase` (例: `getUserInfo`, `totalCount`)
- **组件/类/接口**: `PascalCase` (例: `UserProfile`, `CallData`)
- **常量**: `UPPER_SNAKE_CASE` (例: `API_BASE_URL`)
- **私有成员**: 前缀 `_` 或使用 `#` (例: `_internalState`)
- **布尔值**: 使用 `is/has/should` 前缀 (例: `isLoading`, `hasError`)

### 类型安全
- **禁用 `any`**: 使用 `unknown` 或具体类型
```typescript
// ❌ 错误
const data: any = await fetchData();

// ✅ 正确
const data: CallData = await fetchData();
```
- **严格模式**: `tsconfig.json` 中启用 `strict: true`
- **接口优先**: 定义所有数据结构的接口
```typescript
interface CallRecord {
  id: string;
  callerNumber: string;
  startTime: Date;
  status: 'active' | 'completed' | 'failed';
}
```

### React 组件规范
- **函数组件**: 使用函数组件 + Hooks,不使用类组件
- **Props 接口**: 每个组件必须定义 Props 接口
```typescript
interface CallListProps {
  calls: CallRecord[];
  onCallSelect: (id: string) => void;
  isLoading?: boolean;
}

export const CallList: React.FC<CallListProps> = ({ calls, onCallSelect, isLoading }) => {
  // ...
};
```
- **组件文件**: 一个文件一个组件,文件名与组件名一致

### JSDoc 注释
- **复杂函数添加 JSDoc**:
```typescript
/**
 * 格式化通话时长为可读字符串
 * @param seconds - 通话秒数
 * @returns 格式化后的字符串 (例: "2m 30s")
 */
function formatDuration(seconds: number): string {
  // ...
}
```

### 代码组织
- **使用 Atomic Design**: 组件按 atoms/molecules/organisms/templates 分类
- **自定义 Hooks**: 复用逻辑提取为自定义 Hook (例: `useWebSocket`)
- **避免内联样式**: 使用 CSS 模块或 Carbon 组件的 className

---

## 通用规范

### 注释原则
- **解释 Why,不是 What**: 注释应说明设计决策,而非重复代码
```python
# ❌ 错误: 重复代码
# 创建一个新用户
user = User(name="John")

# ✅ 正确: 解释原因
# 使用 deque 而非 list,因为需要 O(1) 的 append 性能
audio_buffer = deque(maxlen=1000)
```

### 错误处理
- **明确的异常**: 捕获具体异常,避免 `except Exception`
- **日志记录**: 所有异常必须记录日志
- **用户友好**: API 错误返回清晰的错误信息

### 性能意识
- **避免过早优化**: 先保证正确性,再优化性能
- **关键路径优化**: 对延迟敏感的代码(LLM 调用、音频处理)必须优化
- **使用异步**: Backend 所有 I/O 操作必须使用 `async/await`
