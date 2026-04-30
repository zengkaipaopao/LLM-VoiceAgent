# Media Streams Trace 字段说明

最后更新: 2026-04-30

## 1. Trace 存储结构

Twilio Media Streams trace 通过 `app/services/twilio/runtime_backends.py` 中的 `TwilioTraceStore` 写入。

每条事件的基础字段：

```json
{
  "seq": 1,
  "ts": 1777545600000,
  "type": "media_stats",
  "level": "info",
  "text": "frames=100 rms=42 conditioned_rms=42 buffer_ms=19 mode=thin_bridge_stream",
  "final": true
}
```

字段含义：

- `seq`: 同一 `call_sid` 内递增事件序号，前端用它作为 cursor。
- `ts`: 毫秒级 Unix timestamp。
- `type`: 事件类型。
- `level`: `info`、`success`、`warning`、`error`。
- `text`: 事件详情，通常是空格分隔的 `key=value`。
- `final`: 可选字段，表示 transcript 是否为最终文本。

默认保留策略：

- 最多保留 200 个 Call SID。
- 每通电话最多保留 300 条事件。
- 默认内存存储，也支持 Redis backend。

## 2. 关键生命周期事件

### `media_stream_status`

来源：Twilio stream/call status callback。

常见文本：

```text
event=stream-started stream_sid=MZ... timestamp=...
event=stream-stopped stream_sid=MZ... timestamp=...
event=stream-error ...
```

用途：

- 判断 Twilio 是否真的启动/停止媒体流。
- 如果出现 `stream-error`，优先看 Twilio Console 的 Stream SID。

### `stream_start`

来源：自建桥接启动。

常见文本：

```text
prompt=base_appointment route=media_stream_live voice=Aoede activity_mode=auto bridge_profile=cx_agent_studio
```

用途：

- 确认本次通话到底走哪个 prompt、route、voice、bridge profile。

### `live_runtime_config`

来源：桥接 runtime 解析完成。

常见文本：

```text
backend=vertexai modalities=AUDIO session_mode=thin_bridge_realtime route=media_stream_live bridge_profile=cx_agent_studio activity_mode=auto_server_vad activity_handling=start_of_activity_interrupts turn_coverage=all_input ...
```

重点字段：

- `activity_mode`: 当前是 Gemini 自动 VAD 还是手动 activity boundary。
- `activity_handling`: activity start/end 由谁控制。
- `turn_coverage`: 是否上送所有输入音频。
- `input_gate`: 是否开启本地输入门控。
- `manual_start_rms` / `manual_end_rms` / `manual_barge_rms`: 手动边界阈值。
- `silence_duration_ms`: 静音收口目标。
- `outbound_frame_ms`: 回给 Twilio 的帧大小。

排障意义：

- 第二轮没有 input transcript 时，先看这里确认当前是 `auto_server_vad` 还是 `manual_explicit_boundaries`。
- 如果 `input_gate=on`，要额外确认是否把低能量人声过滤掉。

## 3. 入站音频事件

### `media_stats`

来源：后端收到 Twilio `media` 帧后按间隔采样记录。

常见文本：

```text
frames=549 rms=44 conditioned_rms=44 buffer_ms=19 mode=thin_bridge_stream
```

字段：

- `frames`: 已接收 Twilio media 帧数。
- `rms`: 原始解码 PCM8k 的能量。
- `conditioned_rms`: 经过输入门控/处理后的能量。
- `buffer_ms`: 当前转发缓冲。
- `mode`: 当前桥接模式。

排障意义：

- `frames` 持续增加，说明 Twilio 音频还在进后端。
- 第二轮说话时 `rms` 明显升高，说明问题通常不是 Twilio 没发音频。
- `rms` 高但 `conditioned_rms` 长期为 0，优先查 input gate。

### `media_decode_error`

说明 Twilio payload 无法正常 base64/μ-law 解码。

优先检查：

- Twilio payload 格式。
- `audio_codec.py`。
- 是否误把 outbound 音频当 inbound 处理。

### `media_track_ignored`

说明收到了非 inbound track。

通常不是错误，除非 trace 中完全没有 inbound track。

## 4. Gemini transcript 事件

### `input_transcript`

来源：Gemini Live 识别到用户输入。

字段：

- `text`: Gemini 听到的用户文本。
- `final`: 是否最终文本。

判断：

- 第一轮有 `input_transcript final=true`，说明 Gemini 会话、上送音频格式和基础转写能力是通的。
- 第二轮没有任何新的 `input_transcript`，但 `media_stats` 和 followup wav 显示有人声，问题在 turn detection / session state / activity boundary，而不是数据库或前端显示。

### `output_transcript`

来源：Gemini Live 输出文本。

字段：

- `text`: 模型回复转写。
- `final`: 是否最终文本。

注意：

- 当前 UI 里 AI 最近一句经常来自 partial，因此看到“最后一个字”不一定代表模型只返回了最后一个字。
- 判断完整回复应结合多个 `output_transcript` partial、`turn_complete` 和音频播放事件。

## 5. 出站播放事件

### `assistant_audio_started`

说明 Gemini Live 已经开始返回音频。

如果只有这个事件，没有后续 `assistant_audio_forwarded`，优先查音频编码。

### `assistant_audio_forwarded`

常见文本：

```text
mime_type=audio/pcm source_bytes=9600 frames=10 payload_bytes=1600
```

字段：

- `mime_type`: Gemini 返回音频格式。
- `source_bytes`: Gemini PCM 源数据大小。
- `frames`: 切成多少个 Twilio 20ms 帧。
- `payload_bytes`: 发给 Twilio 的 μ-law payload 总大小。

判断：

- 出现该事件说明后端确实把 AI 音频送回 Twilio。
- 如果用户听不到声音但这里正常，要看 `playback_mark_sent` / `playback_complete` 和 Twilio Console。

### `assistant_audio_tail_flushed`

说明尾部不足一帧的音频已经补齐/发送。

### `playback_mark_sent`

说明后端给 Twilio 发送了 mark，用于确认播放完成。

### `playback_mark`

说明 Twilio 回传 mark。

### `playback_complete`

说明后端确认某个 assistant turn 播放完成。

排障意义：

- 如果你要求“不打断 AI 说话”，后续用户输入不应在 `playback_complete` 前触发过强的 clear/barging。
- follow-up probe 通常在 `playback_complete` 后 armed。

## 6. 手动 activity boundary 事件

这些事件只在手动边界模式下最关键。

### `manual_activity_start_sent`

说明后端向 Gemini Live 发送了用户活动开始信号。

常见文本：

```text
raw_rms=1077 conditioned_rms=1077 threshold=900 end_threshold=110 prefix_ms=100 mode=barge_in_during_playback
```

重点：

- `mode=normal_after_playback`: 播放完成后正常开门。
- `mode=barge_in_during_playback`: 播放期间被认为是打断。

### `manual_activity_end_sent`

说明后端向 Gemini Live 发送了用户活动结束信号。

常见文本：

```text
reason=silence_timeout elapsed_ms=356 silence_ms=800 silence_target_ms=800 last_raw_rms=8 last_conditioned_rms=0 ...
```

判断：

- 后续 turn 需要 start 和 end 都稳定出现。
- 如果只有 start 没有 end，Gemini 可能一直等用户说完，导致没有新 turn。

### `manual_activity_progress`

说明当前已经进入用户活动窗口，但还没满足结束条件。

### `manual_activity_silence_reset`

说明刚累计的静音被新的能量打断。

### `manual_activity_end_overdue`

说明 follow-up debug 已经捕获到一段音频，但手动结束边界迟迟没发出。

优先看：

- `silence_ms` 是否长期小于 `silence_target_ms`。
- `last_conditioned_rms` 是否长期高于 `end_rms`。
- `lowest_conditioned_rms` 是否显示其实有足够静音。

## 7. Follow-up probe 事件

### `followup_probe_armed`

说明 AI 播放完成后，后端开始监控后续用户发言。

### `followup_probe_speech_detected`

说明后端在播放完成后检测到了人声能量。

如果它出现了，说明“第二轮完全没进后端”通常不成立。

### `followup_debug_wav_saved`

说明后端已经保存后续轮次调试音频。

常见文本包含：

```text
variant=followup_pcm8k_raw ... path=...
variant=followup_pcm16k_resampled ... path=...
```

用途：

- `followup_pcm8k_raw`: Twilio μ-law 解码后的原始电话音频。
- `followup_pcm16k_resampled`: 真正送给 Gemini Live 前的 16k PCM。

### `gemini_turn_detection_stalled`

说明后端检测到后续人声，也保存了 debug wav，但 Gemini Live 没有提交新输入转写。

这是排查“第二轮不被识别”的核心证据。

下一步：

- 回放 follow-up wav。
- 用 audio lab 直接送 Gemini Live。
- 对照 `live_runtime_config` 判断是自动 VAD 还是手动 boundary。
- 如果离线可识别但在线不可识别，优先查 session state / boundary / playback timing。
- 如果离线也不可识别，优先查转码、采样率、音频质量。

## 8. 重叠和打断事件

### `duplex_overlap_detected`

说明助手播放窗口内又检测到了入站能量。

常见文本：

```text
rms=189 assistant_phase=playback_pending pending_mark=assistant-turn-1
```

判断：

- 不一定是错误。电话回声、环境声、用户抢话都会触发。
- 如果和 `gemini_turn_detection_stalled` 同时出现，要重点看是否过早 clear 或手动 start。

### `assistant_audio_dropped_after_local_barge_in`

说明本地认为用户打断后，丢弃了后续 AI 音频。

如果当前策略是不打断 AI，要避免该事件在正常用户背景声下出现。

### `interrupted`

说明 Gemini / 本地播放策略认为当前回复被打断。

## 9. Debug wav 事件

### `inbound_debug_wav_saved`

通常在 stream stop 时保存最近一段入站音频。

用途：

- 验证整通电话最后阶段的音频质量。
- 对比 PCM8k raw 与 PCM16k resampled。

### `followup_debug_wav_saved`

用于第二轮排障，优先级通常高于 `inbound_debug_wav_saved`。

## 10. 常见判断模板

### 第二轮没有转写

如果 trace 满足：

```text
playback_complete
followup_probe_armed
followup_probe_speech_detected
followup_debug_wav_saved
gemini_turn_detection_stalled
```

判断：

- Twilio 到后端音频是通的。
- 后端已经捕获第二轮候选音频。
- Gemini Live 没有把这一段提交成新 turn。

继续分叉：

- follow-up wav 清晰且 audio lab 可识别：查在线 turn boundary/session/playback。
- follow-up wav 不清晰或 audio lab 不可识别：查 μ-law 解码、resample、输入门控和音频质量。

### AI 没有声音

如果 trace 有：

```text
output_transcript
assistant_audio_started
```

但没有：

```text
assistant_audio_forwarded
playback_mark_sent
playback_complete
```

判断：

- Gemini 已产出内容，但后端回程音频或 Twilio 播放确认有问题。

### 电话刚接通就断

优先看：

```text
configuration_error
stream_error
call_status_error
media_stream_status event=stream-error
```

并结合后端异常堆栈。
