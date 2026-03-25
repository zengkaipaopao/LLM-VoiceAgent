# 前端 API 契约与数据交互设计规范 (Frontend API Contract Design)

为了在前后端交互之间建立坚如磐石的边界，彻底消除隐式的数据类型转换、危险的 `any` 强转以及难以维护的遗留字段兼容代码，特指定本契约设计规范。今后所有的前端 API 模块开发必须遵循此规范。

## 1. 核心设计原则

1. **边界防御与运行时校验 (Run-time Validation)**: TypeScript 的类型（Interfaces/Types）只在编译期有效，无法保证运行时后端返回的数据格式一定正确。必须使用 **Zod** （或其他验证库）在 API 边界处对请求和响应数据进行严格的运行时格式校验与解析。
2. **DTO (Data Transfer Object) 模式分离**: 
   - **后端 API 响应 (API Schema)**: 反映后端真实返回的 JSON 结构（包含蛇形命名 `snake_case`、可能存在的遗留冗余字段）。
   - **前端领域模型 (Domain Model)**: 反映前端 UI 组件消费的干净数据结构（严格的驼峰命名 `camelCase`，无废弃字段）。
   - **必须在 API 层实现显式的双向映射**：`API Schema <-> Domain Model`。
3. **统一包装结构**: 严格遵循《API 设计规范》(api-design-guide.md) 中的统一响应体结构（`success`, `data`, `meta`, `error`）。任何偏离该结构的响应都应在统一的响应拦截器中被拒绝。

---

## 2. 基础响应拦截与错误处理

前端 HTTP 客户端（如 Axios/Fetch）必须配置统一的拦截器，只返回 `success: true` 且解包后的 `data`，或者抛出标准的标准错误对象。

```typescript
// src/api/http.ts 拦截器伪代码示例
import axios from 'axios';
import { ApiError } from '../types/errors';

export const http = axios.create({ ... });

http.interceptors.response.use(
  (response) => {
    const { success, data, error, meta } = response.data;
    if (success) {
      // 成功，直接返回原始 payload（未处理的具体数据），由具体的 API 函数进行 Zod 解析
      return data; 
    } else {
      // 业务级别的失败（HTTP 200，但 success=false）
      return Promise.reject(new ApiError(error.code, error.message, error.details));
    }
  },
  (error) => {
    // 网络级、HTTP 级错误 (4xx, 500 等)
    const errData = error.response?.data?.error;
    return Promise.reject(
      new ApiError(errData?.code || 'NETWORK_ERROR', errData?.message || error.message, errData?.details)
    );
  }
);
```

---

## 3. Zod 数据清洗与 DTO 映射实战规范

在具体的 API 源文件（如 `prompts.ts`, `calls.ts`）中，废弃原本手动的 `JSON.parse` 尝试和属性拼接，改用 Zod Schema 声明。

### 3.1 定义 Zod Schema 并推导类型

定义后端返回的原始数据 Schema，这里会自动剔除未声明的冗余字段，并对必填项进行强制校验。

```typescript
import { z } from 'zod';

// 1. 定义后端返回数据的格式 (API Schema)
// 使用 Zod 解析可以自动处理 JSON 字符串的可选解析，消除 tryParseJson 的丑陋代码
export const ApiPromptSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  code: z.string(),
  description: z.string().optional(),
  
  llm_provider: z.string().default('gemini'),
  llm_model: z.string().default('gemini-2.0-flash'),
  
  system_prompt: z.string(),
  
  // 对于后端可能是 string(序列化JSON) 或 对象的情况，使用 preprocess 优雅处理
  extraction_schema: z.preprocess((val) => {
    if (typeof val === 'string') {
      try { return JSON.parse(val); } catch { return undefined; }
    }
    return val;
  }, z.record(z.any()).optional()),
  
  voice_config: z.object({
    voice: z.string().optional(),
    speaking_rate: z.number().optional()
  }).optional(),
  
  updated_at: z.string(),
  is_active: z.boolean()
});

// Infer Type (可选，仅在需要时)
export type ApiPrompt = z.infer<typeof ApiPromptSchema>;
```

### 3.2 映射到前端领域模型 (Mapper)

前端 UI 使用的模型类型统一定义在 `src/types/shared.ts` 中。在 API 层提供纯净的转换函数：

```typescript
// 将解析过的安全 ApiPrompt 转化为 前端使用的 PromptTemplate
export const mapPromptToDomain = (data: unknown): PromptTemplate => {
  // 第一步：运行时安全解析（抛出异常或剔除无效/脏数据）
  const parsed = ApiPromptSchema.parse(data);

  // 第二步：安全的字段映射，转化为前端标准的 camelCase 和清洁的业务模型
  return {
    id: parsed.id,
    name: parsed.name,
    code: parsed.code,
    description: parsed.description,
    
    llmProvider: parsed.llm_provider,
    llmModel: parsed.llm_model,
    systemPrompt: parsed.system_prompt,
    extractionSchema: parsed.extraction_schema,
    
    voiceConfig: parsed.voice_config ? {
      voice: parsed.voice_config.voice,
      speakingRate: parsed.voice_config.speaking_rate,
    } : undefined,
    
    updatedAt: parsed.updated_at,
    isActive: parsed.is_active,
  };
};
```

### 3.3 在 API 调用中使用

```typescript
export async function fetchPrompts(): Promise<PromptTemplate[]> {
  // 此时 http.get 已被拦截器处理，直接返回 data 字典中的 templates 数组
  const data = await http.get('/prompts'); 
  const templates = data.templates || [];
  
  // 遍历强制转化，任何不符合格式的脏数据将在 mapping 阶段被识别和处理
  return templates.map(mapPromptToDomain);
}
```

---

## 4. 表单与数据提交规范

从前端向后端发送数据时，同样的，也需要经过校验并转换为后端接受的 API 格式：

```typescript
export const PromptSubmitSchema = z.object({
  name: z.string().min(1, '名称不能为空'),
  code: z.string(),
  llmProvider: z.string(),
  systemPrompt: z.string(),
  // ... 前端表单状态
});

export const mapDomainToApiSubmit = (domainPayload: unknown) => {
  // 校验前端填写的表单，如果内部有错误，抛错交给 React Hook Form 等处理
  const validData = PromptSubmitSchema.parse(domainPayload);
  
  // 转化为后端的蛇形请求格式
  return {
    name: validData.name,
    code: validData.code,
    llm_provider: validData.llmProvider,
    system_prompt: validData.systemPrompt
  };
};

export async function createPrompt(payload: PromptFormValues) {
  const apiPayload = mapDomainToApiSubmit(payload);
  const data = await http.post('/prompts', apiPayload);
  return mapPromptToDomain(data); // 转化返回结果
}
```

## 5. 设计总结

1. **废弃所有的硬编码 `any` 转换**，在 src/api 库下全面引入 Zod 隔离。
2. **前后端解耦**：当后端需要增加废弃兼容字段（比如旧的 `instructions`），在 Zod `preprocess` 或者映射阶段消费并抹除它，绝对不允许废弃字段渗透进入前端组件库，影响 UI 逻辑（不再出现 `item.instructions ?? item.system_prompt` 写在组件里的情况）。
3. **单一信任源**：以 Zod Schema 为基础防线。如果 Zod 报错，可以通过 React Query 的 Error Boundary 进行全局友好拦截提示，并在 Console 清楚展示数据格式错误的原因。
