---
name: 异步性能优化
description: Python asyncio 性能分析和优化指南,识别阻塞 I/O 和提升并发性能
---

# 异步性能优化技能

## 何时使用此技能

当用户提到以下关键词时激活:
- "性能优化"
- "延迟"
- "慢"
- "并发"
- "阻塞"
- "asyncio"
- "Time-to-First-Token"

## 核心原则

### 1. 严格异步 - 禁止阻塞 I/O

**❌ 常见错误**:
```python
import time
import requests

async def bad_example():
    time.sleep(1)  # 阻塞整个事件循环!
    response = requests.get(url)  # 同步 HTTP 调用!
```

**✅ 正确做法**:
```python
import asyncio
import httpx

async def good_example():
    await asyncio.sleep(1)  # 非阻塞
    async with httpx.AsyncClient() as client:
        response = await client.get(url)  # 异步 HTTP
```

### 2. 并行化 I/O 操作

**❌ 串行执行**:
```python
async def slow():
    user = await fetch_user(user_id)  # 等待 100ms
    calls = await fetch_calls(user_id)  # 等待 150ms
    # 总耗时: 250ms
```

**✅ 并行执行**:
```python
async def fast():
    user, calls = await asyncio.gather(
        fetch_user(user_id),
        fetch_calls(user_id)
    )
    # 总耗时: max(100ms, 150ms) = 150ms
```

### 3. 使用队列解耦生产者和消费者

```python
audio_queue = asyncio.Queue(maxsize=100)

async def audio_receiver(websocket):
    """生产者: 接收音频"""
    while True:
        chunk = await websocket.receive_bytes()
        await audio_queue.put(chunk)

async def audio_processor():
    """消费者: 处理音频"""
    while True:
        chunk = await audio_queue.get()
        await process_audio(chunk)
        audio_queue.task_done()

# 并发运行
await asyncio.gather(
    audio_receiver(ws),
    audio_processor()
)
```

## 性能分析工具

### 1. 识别阻塞调用

使用 `asyncio` 的调试模式:
```python
import asyncio
import warnings

# 启用调试模式
asyncio.run(main(), debug=True)

# 或设置环境变量
# PYTHONASYNCIODEBUG=1 python app.py
```

调试模式会警告:
- 执行时间超过 100ms 的协程
- 未 await 的协程
- 未正确关闭的资源

### 2. 性能分析

```python
import time

async def profile_async_function():
    start = time.perf_counter()
    result = await some_async_function()
    elapsed = time.perf_counter() - start
    print(f"耗时: {elapsed*1000:.2f}ms")
    return result
```

## 常见性能陷阱

### 陷阱 1: 在循环中 await

**❌ 慢**:
```python
for item in items:
    await process(item)  # 串行处理
```

**✅ 快**:
```python
await asyncio.gather(*[process(item) for item in items])
```

### 陷阱 2: 过度使用锁

**❌ 慢**:
```python
lock = asyncio.Lock()
async def process():
    async with lock:  # 所有请求串行化
        await do_work()
```

**✅ 快**: 使用无锁数据结构或队列

### 陷阱 3: 忘记设置超时

```python
# ✅ 始终设置超时
try:
    response = await asyncio.wait_for(
        llm_client.generate(prompt),
        timeout=30.0
    )
except asyncio.TimeoutError:
    logger.error("LLM 调用超时")
```

## 优化 LLM 调用延迟

### 1. 流式响应

```python
async def stream_llm_response(prompt: str):
    """使用流式 API 减少 Time-to-First-Token"""
    async for chunk in llm_client.stream(prompt):
        yield chunk  # 立即返回第一个 token
```

### 2. 预热连接

```python
# 应用启动时预热 HTTP 连接池
async def warmup():
    async with httpx.AsyncClient() as client:
        await client.get("https://api.openai.com/v1/models")
```

### 3. 缓存常见响应

```python
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_cached_prompt(prompt_id: str):
    return await prompt_repo.get_by_id(prompt_id)
```

## 参考资料

- [best-practices.md](file:///Users/zeng/Desktop/LLM-VoiceAgent/.agent/skills/async-performance/references/best-practices.md) - 详细的最佳实践文档
- 项目架构文档: [docs/ARCHITECTURE.md](file:///Users/zeng/Desktop/LLM-VoiceAgent/docs/ARCHITECTURE.md)
