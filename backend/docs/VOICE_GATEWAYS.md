# 语音网关链路说明

最后更新: 2026-04-30

## 1. 目标

本文档说明后端当前维护的三类语音接入链路，以及它们和 Gemini、Twilio、测试台、预约落库之间的边界。

当前语音链路不是同一种实现的不同开关，而是三条职责不同的路径：

- 浏览器直连 Gemini Live：用于测试台和浏览器语音能力验证。
- 官方 Conversational Agents / CX Agent Studio：用于官方托管链路对照。
- Twilio Media Streams 自建桥接：用于验证后端自控电话音频桥。

## 2. 浏览器直连 Gemini Live

入口：

```text
frontend voice test
-> /api/v1/live/ws
-> app/api/v1/endpoints/realtime.py
-> app/services/live_gateway/browser_websocket_bridge.py
-> app/services/live_gateway/browser_realtime.py
-> Gemini Live
```

职责：

- 建立浏览器 WebSocket。
- 解析 Prompt runtime、模型、音色、modalities。
- 转发浏览器采集的音频/text 到 Gemini Live。
- 将 Gemini Live 的文本、音频、turn 事件转回前端。
- 结束时通过测试会话 finalize 进入抽取和预约落库。

不负责：

- Twilio webhook。
- 电话 μ-law 转码。
- Media Streams trace。
- 预约取消/变更目标匹配细节。

主要文件：

```text
app/api/v1/endpoints/realtime.py
app/services/live_gateway/browser_websocket_bridge.py
app/services/live_gateway/browser_realtime.py
app/services/test_session_service.py
app/services/extraction/appointment_application_service.py
```

## 3. 官方 Conversational Agents / CX Agent Studio

入口：

```text
Twilio incoming webhook
-> app/services/twilio/incoming_service.py
-> official conversational agents route
-> Twilio official connector / Google CX Agent Studio
-> status callback
-> finalize / extraction
```

职责：

- 作为官方链路基线。
- 尽量少做本地音频和 turn detection 控制。
- 用来判断问题是在本地 Media Streams 桥，还是上游模型/电话环境。

主要文件：

```text
app/services/twilio/official_conversational_agents.py
app/services/twilio/incoming_service.py
app/services/twilio/status_service.py
```

注意：

- CX Agent Studio 平台侧 Prompt/Agent 可能和本地 PromptTemplate 不完全一致。
- 这条链路能稳定多轮，不代表自建 Media Streams 的音频帧、turn boundary、playback/clear 行为也正确。
- 它更适合作为商业稳定性基线和排障对照组。

## 4. Twilio Media Streams 自建桥接

入口：

```text
Twilio incoming webhook
-> /api/v1/twilio/voice/incoming
-> TwilioIncomingService builds <Connect><Stream>
-> /api/v1/twilio/voice/stream WebSocket
-> TwilioMediaStreamWebSocketService
-> run_twilio_media_stream_bridge()
-> Gemini Live
-> Twilio outbound audio
```

职责：

- 接收 Twilio Media Streams 的 `audio/x-mulaw; rate=8000` 音频帧。
- 解码、升采样、转发到 Gemini Live。
- 接收 Gemini Live PCM 音频，降采样、μ-law 编码后回传 Twilio。
- 写入 trace、media stats、debug wav、diagnostics。
- 在通话结束后触发 finalize / extraction。

主要文件：

```text
app/api/v1/endpoints/twilio_legacy_stream.py
app/services/twilio/media_stream_websocket_service.py
app/services/twilio/media_stream_bridge_service.py
app/services/twilio/audio_codec.py
app/services/twilio/trace_service.py
app/services/twilio/trace_diagnostics.py
app/services/twilio/audio_lab.py
```

当前原则：

- API endpoint 只保留 WebSocket 边界。
- runtime 解析在 `media_stream_websocket_service.py`。
- 音频桥长循环在 `media_stream_bridge_service.py`。
- 音频诊断和离线实验在 `trace_service.py` / `audio_lab.py`。
- 不在 Media Streams 模块里实现预约匹配状态机。

## 5. 预约落库边界

三条语音链路最终都应该回到统一的业务服务：

```text
transcript / test session
-> AppointmentExtractionApplicationService
-> AppointmentExtractionApplier
-> AppointmentOperationFlowService / Executor
-> AppointmentRepository
```

这条边界的目的：

- 预约创建、变更、取消只维护一套规则。
- 浏览器直连、官方 CX、自建 Media Streams 不各自写数据库逻辑。
- 取消和变更的目标匹配不会被语音网关实现细节污染。

## 6. 排障顺序

多轮语音问题建议按这个顺序判断：

1. 官方 CX 链路是否稳定多轮。
2. 浏览器直连 Gemini Live 是否稳定多轮。
3. Media Streams trace 是否有第二轮 inbound audio。
4. debug wav 中 PCM8k / PCM16k 是否能听清。
5. 离线 audio lab 直接送 Gemini Live 是否能得到 input transcript。
6. 如果离线可识别但在线不可识别，优先查 Media Streams turn boundary / session state。
7. 如果离线也不可识别，优先查转码、采样率、音频质量。

Trace 字段和事件类型详见：

```text
backend/docs/MEDIA_STREAM_TRACE_FIELDS.md
```

## 7. 不要做的事

- 不要把 Media Streams 的临时调参逻辑写进 `ChatService`。
- 不要让 Twilio endpoint 直接写预约数据库。
- 不要让 PromptTemplate 承担确定性数据库操作。
- 不要在 WebSocket 音频循环里做阻塞 I/O。
- 不要混用官方 CX 的行为假设去掩盖自建桥接的 trace 证据。
