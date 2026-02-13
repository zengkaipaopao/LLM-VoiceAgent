---
name: WebSocket 实时连接调试
description: 提供 WebSocket 连接测试和调试工具,用于验证实时音频流和消息传输
---

# WebSocket 实时连接调试技能

## 何时使用此技能

当用户提到以下关键词时激活:
- "WebSocket"
- "实时连接"
- "ws://"
- "音频流"
- "连接测试"
- "调试实时通话"

## 功能说明

此技能提供工具和脚本来测试和调试 WebSocket 实时连接,特别是针对 `/ws/realtime` 端点的音频流传输。

## 使用方法

### 1. 使用测试脚本

项目提供了 WebSocket 测试客户端脚本 `scripts/ws_test_client.py`,可以:
- 连接到 WebSocket 端点
- 发送模拟音频数据
- 接收和验证服务器响应
- 测试消息格式

运行脚本:
```bash
cd backend
python scripts/ws_test_client.py --url ws://localhost:8000/ws/realtime
```

### 2. 浏览器开发者工具

使用浏览器的 Network 标签:
1. 打开开发者工具 (F12)
2. 切换到 Network 标签
3. 过滤 WS (WebSocket)
4. 查看连接状态、发送/接收的消息

### 3. 常见问题排查

**连接失败**:
- 检查服务器是否运行: `curl http://localhost:8000/health`
- 验证 URL 正确: `ws://` (开发) 或 `wss://` (生产)
- 检查 CORS 配置

**消息格式错误**:
- 验证 JSON 格式: 使用 `json.dumps()` 序列化
- 检查必需字段: `type`, `data` 等
- 参考 `app/schemas/realtime.py` 中的消息模型

**音频数据问题**:
- 确认音频格式: PCM16, 采样率 16kHz
- 检查 Base64 编码: 音频数据需要 Base64 编码
- 验证数据大小: 每个 chunk 不超过 64KB

## 消息格式参考

### 客户端 → 服务器

```json
{
  "type": "audio",
  "data": {
    "audio": "base64_encoded_audio_data",
    "sample_rate": 16000,
    "channels": 1
  }
}
```

### 服务器 → 客户端

```json
{
  "type": "transcript",
  "data": {
    "text": "识别的文本",
    "is_final": true,
    "confidence": 0.95
  }
}
```

## 相关文件

- 测试脚本: `backend/scripts/ws_test_client.py`
- 消息模型: `backend/app/schemas/realtime.py`
- WebSocket 端点: `backend/app/api/v1/endpoints/realtime.py`
