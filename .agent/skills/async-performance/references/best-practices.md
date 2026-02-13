# 异步编程最佳实践

## 反模式和解决方案

### 反模式 1: 混用同步和异步代码

**问题**:
```python
async def bad_handler():
    data = sync_database_query()  # 阻塞!
    result = await async_process(data)
```

**解决方案**:
```python
async def good_handler():
    # 使用 asyncio.to_thread 在线程池中运行同步代码
    data = await asyncio.to_thread(sync_database_query)
    result = await async_process(data)
```

### 反模式 2: 忘记 await

**问题**:
```python
async def bad():
    result = async_function()  # 返回协程对象,未执行!
    print(result)  # <coroutine object ...>
```

**解决方案**:
```python
async def good():
    result = await async_function()  # 正确执行
    print(result)
```

### 反模式 3: 在 __init__ 中使用 async

**问题**:
```python
class BadService:
    def __init__(self):
        self.data = await self.fetch_data()  # 语法错误!
```

**解决方案**:
```python
class GoodService:
    def __init__(self):
        self.data = None
    
    async def initialize(self):
        self.data = await self.fetch_data()
        return self

# 使用
service = await GoodService().initialize()
```

## 任务管理

### 使用 TaskGroup (Python 3.11+)

```python
async def process_multiple():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(process_a())
        task2 = tg.create_task(process_b())
        task3 = tg.create_task(process_c())
    
    # 所有任务完成或任一任务失败时退出
    # 自动取消未完成的任务
```

### 后台任务

```python
background_tasks = set()

async def start_background_task(coro):
    """启动后台任务并防止被垃圾回收"""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
```

## 错误处理

### 捕获所有任务的异常

```python
async def safe_gather(*coros):
    """gather 的安全版本,返回结果和异常"""
    results = await asyncio.gather(*coros, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Task {i} failed: {result}")
    
    return [r for r in results if not isinstance(r, Exception)]
```

### 优雅关闭

```python
async def graceful_shutdown():
    """取消所有运行中的任务"""
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
```

## 性能优化技巧

### 1. 使用 asyncio.as_completed

当需要尽快处理完成的任务时:
```python
tasks = [fetch_data(i) for i in range(10)]

for coro in asyncio.as_completed(tasks):
    result = await coro
    process_immediately(result)  # 不等待其他任务
```

### 2. 限制并发数

```python
from asyncio import Semaphore

semaphore = Semaphore(5)  # 最多 5 个并发

async def limited_fetch(url):
    async with semaphore:
        return await fetch(url)

# 虽然创建 100 个任务,但同时只运行 5 个
await asyncio.gather(*[limited_fetch(url) for url in urls])
```

### 3. 连接池管理

```python
# ✅ 复用连接池
client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=30.0
)

async def fetch_many():
    results = await asyncio.gather(*[
        client.get(url) for url in urls
    ])
    return results

# 应用关闭时清理
await client.aclose()
```

## 调试技巧

### 1. 打印任务状态

```python
def print_task_status():
    tasks = asyncio.all_tasks()
    print(f"运行中的任务: {len(tasks)}")
    for task in tasks:
        print(f"  - {task.get_name()}: {task._state}")
```

### 2. 检测慢协程

```python
import functools
import time

def log_slow_coroutines(threshold_ms=100):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            if elapsed_ms > threshold_ms:
                logger.warning(
                    f"{func.__name__} took {elapsed_ms:.2f}ms (threshold: {threshold_ms}ms)"
                )
            
            return result
        return wrapper
    return decorator

@log_slow_coroutines(threshold_ms=50)
async def potentially_slow_function():
    await some_operation()
```

## WebSocket 特定优化

### 1. 心跳保活

```python
async def heartbeat(websocket, interval=30):
    """定期发送心跳防止连接超时"""
    while True:
        try:
            await asyncio.sleep(interval)
            await websocket.send_json({"type": "ping"})
        except Exception:
            break
```

### 2. 缓冲区管理

```python
from collections import deque

class AudioBuffer:
    def __init__(self, maxlen=100):
        self.buffer = deque(maxlen=maxlen)
    
    async def add(self, chunk):
        self.buffer.append(chunk)
        if len(self.buffer) >= self.buffer.maxlen:
            logger.warning("Buffer full, dropping old chunks")
    
    async def get_all(self):
        chunks = list(self.buffer)
        self.buffer.clear()
        return chunks
```
