from __future__ import annotations

import time
from typing import Any


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _lowered_text(value: object) -> str:
    return _normalized_text(value).lower()


def _build_diagnostic(
    *,
    call_sid: str,
    status: str,
    category: str,
    owner: str,
    title: str,
    summary: str,
    actions: list[str],
    evidence_events: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence = [
        {
            "seq": int(item.get("seq", 0)),
            "ts": int(item.get("ts", 0)),
            "type": _normalized_text(item.get("type")),
            "level": _normalized_text(item.get("level")) or "info",
            "text": _normalized_text(item.get("text")),
        }
        for item in evidence_events[:3]
    ]
    return {
        "call_sid": call_sid,
        "status": status,
        "category": category,
        "owner": owner,
        "title": title,
        "summary": summary,
        "actions": actions,
        "evidence": evidence,
    }


def build_twilio_trace_diagnostic(
    *,
    call_sid: str,
    events: list[dict[str, Any]],
    stream_active: bool,
) -> dict[str, Any]:
    ordered_events = sorted(events, key=lambda item: int(item.get("seq", 0)))
    reversed_events = list(reversed(ordered_events))
    now_ms = int(time.time() * 1000)

    error_events = [item for item in reversed_events if _lowered_text(item.get("level")) == "error"]
    warning_events = [item for item in reversed_events if _lowered_text(item.get("level")) == "warning"]

    for event in error_events:
        event_type = _normalized_text(event.get("type"))
        text = _normalized_text(event.get("text"))
        lowered = text.lower()

        if event_type == "configuration_error":
            return _build_diagnostic(
                call_sid=call_sid,
                status="error",
                category="backend_configuration",
                owner="backend",
                title="后端配置阻止媒体桥接启动",
                summary=text or "Twilio Media Streams 配置不符合当前生产桥接要求。",
                actions=[
                    "检查后端环境变量，确保 TWILIO_GEMINI_ACTIVITY_MODE=auto。",
                    "重新启动后端后再发起通话，确认不再出现 configuration_error。",
                ],
                evidence_events=[event],
            )

        if event_type == "call_status_error":
            return _build_diagnostic(
                call_sid=call_sid,
                status="error",
                category="twilio_call_status",
                owner="twilio",
                title="Twilio 电话状态回调返回错误",
                summary=text or "Twilio 已明确返回通话级错误状态。",
                actions=[
                    "查看 Twilio Console 里该 Call SID 的错误码与呼叫日志。",
                    "核对号码、Webhook、地区权限和资费限制。",
                ],
                evidence_events=[event],
            )

        if event_type == "stream_error":
            if "default credentials were not found" in lowered or "application default credentials" in lowered:
                return _build_diagnostic(
                    call_sid=call_sid,
                    status="error",
                    category="google_adc_missing",
                    owner="google_cloud_auth",
                    title="Vertex AI ADC 凭证缺失",
                    summary="后端已经接到电话，但 Gemini Live 无法建立会话，因为运行环境没有可用的 Application Default Credentials。",
                    actions=[
                        "为当前后端进程配置 GOOGLE_APPLICATION_CREDENTIALS，或在运行环境中完成 gcloud auth application-default login。",
                        "确认后端进程实际读取到的凭证身份与预期服务账号一致。",
                    ],
                    evidence_events=[event],
                )
            if "aiplatform.endpoints.predict" in lowered or "permission denied" in lowered:
                return _build_diagnostic(
                    call_sid=call_sid,
                    status="error",
                    category="google_vertex_permission",
                    owner="google_cloud_iam",
                    title="Vertex AI 调用权限不足",
                    summary="后端可以拿到凭证，但当前身份没有足够权限调用 Gemini Live / Vertex AI 预测接口。",
                    actions=[
                        "检查当前后端服务账号是否拥有 roles/aiplatform.user 或等价可调用权限。",
                        "确认后端使用的 ADC 身份就是你刚授权的那个服务账号，而不是别的本地身份。",
                    ],
                    evidence_events=[event],
                )
            if "publisher model" in lowered or "model" in lowered and ("not found" in lowered or "unsupported" in lowered):
                return _build_diagnostic(
                    call_sid=call_sid,
                    status="error",
                    category="gemini_model_configuration",
                    owner="model_configuration",
                    title="Gemini Live 模型配置错误",
                    summary="电话已经接通，但后端请求的 Gemini Live 模型在当前区域或当前后端模式下不可用。",
                    actions=[
                        "检查 Prompt 的 llm_model 与后端默认 live model 是否映射到了当前可用的 Vertex Live 模型。",
                        "确认模型所在区域与 GOOGLE_CLOUD_LOCATION 一致。",
                    ],
                    evidence_events=[event],
                )
            return _build_diagnostic(
                call_sid=call_sid,
                status="error",
                category="media_stream_bridge_runtime",
                owner="backend_bridge",
                title="电话媒体桥接在后端运行时失败",
                summary=text or "Twilio Media Streams 与 Gemini Live 的桥接协程在运行时发生异常。",
                actions=[
                    "查看后端日志中的完整堆栈，确认是 WebSocket、模型、提取收尾还是音频编码阶段失败。",
                    "对照下方证据事件与 Call SID，定位具体失败点。",
                ],
                evidence_events=[event, *warning_events[:2]],
            )

        if event_type == "assistant_audio_encode_error":
            return _build_diagnostic(
                call_sid=call_sid,
                status="error",
                category="assistant_audio_encode",
                owner="backend_audio_pipeline",
                title="模型音频无法编码回 Twilio",
                summary="Gemini Live 已经产出音频片段，但后端在转成 Twilio 可播放的 8k μ-law 音频时失败。",
                actions=[
                    "检查模型返回的 inline audio mime_type 和采样率。",
                    "检查后端音频编码实现和最近一次相关代码改动。",
                ],
                evidence_events=[event],
            )

        if event_type == "assistant_audio_empty":
            return _build_diagnostic(
                call_sid=call_sid,
                status="warning",
                category="assistant_audio_empty",
                owner="backend_audio_pipeline",
                title="模型产出了音频片段，但没有成功形成可播帧",
                summary="Gemini Live 已返回音频数据，但后端在当前片段上没有实际生成发往 Twilio 的 μ-law 帧，因此电话另一端可能听不到声音。",
                actions=[
                    "检查当前模型返回的 inline audio 大小、mime_type 和采样率。",
                    "继续观察 assistant_audio_forwarded、playback_mark_sent、playback_complete 是否出现。",
                ],
                evidence_events=[event],
            )

        if event_type == "media_stream_status" and "stream-error" in lowered:
            return _build_diagnostic(
                call_sid=call_sid,
                status="error",
                category="twilio_media_stream_transport",
                owner="twilio_transport",
                title="Twilio Media Stream 传输层报错",
                summary=text or "Twilio 在媒体流状态回调里报告了 stream-error。",
                actions=[
                    "查看 Twilio Console 中该 Stream SID 的错误详情。",
                    "检查 WebSocket URL、TLS 证书、ngrok/反向代理和后端连通性。",
                ],
                evidence_events=[event],
            )

    for event in warning_events:
        event_type = _normalized_text(event.get("type"))
        text = _normalized_text(event.get("text"))

        if event_type == "assistant_turn_without_audio":
            return _build_diagnostic(
                call_sid=call_sid,
                status="warning",
                category="assistant_turn_without_audio",
                owner="gemini_or_prompt",
                title="模型完成了回合，但没有输出可播放语音",
                summary="Gemini Live 已结束当前 turn，但本次没有产生音频片段，所以电话另一端不会听到声音。",
                actions=[
                    "检查当前 Prompt 是否明确要求模型用语音回复，并避免只返回元文本。",
                    "检查所选模型与音色是否支持 Native Audio 输出。",
                ],
                evidence_events=[event],
            )

        if event_type == "media_stream_status" and "stream-stopped" in text and stream_active:
            return _build_diagnostic(
                call_sid=call_sid,
                status="warning",
                category="twilio_stream_unexpected_stop",
                owner="twilio_transport",
                title="Twilio 媒体流提前停止",
                summary="媒体流状态回调显示已经 stop，但当前测试页仍认为这通电话需要继续跟踪。",
                actions=[
                    "检查 Twilio 侧是否因为通话结束、超时或 WebSocket 断开而提前停止媒体流。",
                    "核对拨号链路日志和状态回调顺序。",
                ],
                evidence_events=[event],
            )

    if not ordered_events:
        return _build_diagnostic(
            call_sid=call_sid,
            status="unknown",
            category="no_trace_events",
            owner="unknown",
            title="尚未收到诊断事件",
            summary="当前 Call SID 还没有 trace 事件，可能电话尚未真正进入媒体桥接，或 trace 尚未开始写入。",
            actions=[
                "确认电话是否已接通并进入 Media Streams 路径。",
                "确认测试页里的 Bound Call SID 与实际通话 SID 一致。",
            ],
            evidence_events=[],
        )

    latest_event = ordered_events[-1]
    latest_event_ts = int(latest_event.get("ts", 0) or 0)
    has_stream_start = any(_normalized_text(item.get("type")) == "stream_start" for item in ordered_events)
    has_assistant_audio_started = any(
        _normalized_text(item.get("type")) == "assistant_audio_started" for item in ordered_events
    )
    has_assistant_audio = any(
        _normalized_text(item.get("type")) in {
            "assistant_audio_forwarded",
            "playback_mark_sent",
            "playback_complete",
        }
        for item in ordered_events
    )
    has_user_activity = any(
        _normalized_text(item.get("type")) in {"input_transcript", "interrupted"}
        for item in ordered_events
    )

    if stream_active and has_stream_start and not has_assistant_audio and latest_event_ts > 0 and (now_ms - latest_event_ts) >= 6000:
        return _build_diagnostic(
            call_sid=call_sid,
            status="warning",
            category="assistant_not_responding",
            owner="backend_or_model",
            title="电话已接通，但模型迟迟没有发出语音",
            summary="链路已经进入媒体桥接，但在最近几秒内没有看到模型音频输出事件。",
            actions=[
                "先看下方证据里最后几条事件，确认是否只有 opening 请求或用户转写而没有 assistant_audio_started。",
                "优先排查 Prompt、模型、音色配置，以及 Gemini Live 会话是否真正建立成功。",
            ],
            evidence_events=reversed_events[:3],
        )

    if stream_active and has_assistant_audio_started and not has_assistant_audio:
        return _build_diagnostic(
            call_sid=call_sid,
            status="warning",
            category="assistant_audio_not_playing",
            owner="backend_audio_pipeline",
            title="模型已经开始产出音频，但电话侧还没有看到实际播放迹象",
            summary="Trace 中已有 assistant_audio_started，但没有看到真正发往 Twilio 的音频帧或播放确认事件。",
            actions=[
                "优先检查 assistant_audio_empty、assistant_audio_encode_error 是否出现。",
                "确认 Twilio Media Streams 回程音频格式仍是 μ-law 8k，并观察 playback_mark_sent / playback_complete 是否缺失。",
            ],
            evidence_events=reversed_events[:4],
        )

    if stream_active and has_user_activity and not has_assistant_audio:
        return _build_diagnostic(
            call_sid=call_sid,
            status="warning",
            category="user_heard_no_reply",
            owner="backend_or_model",
            title="用户已经说话，但还没有看到模型语音回包",
            summary="Trace 中已有用户发言相关事件，但还没有看到 Gemini Live 输出音频。",
            actions=[
                "检查 Gemini Live 会话是否支持音频输出，而不是只有文本转写。",
                "检查最近一次模型 turn_complete 是否带了 assistant_turn_without_audio。",
            ],
            evidence_events=reversed_events[:3],
        )

    return _build_diagnostic(
        call_sid=call_sid,
        status="ok" if stream_active else "warning",
        category="healthy",
        owner="system",
        title="当前电话链路未见明确故障",
        summary="从现有 trace 看，媒体桥接正在运行，暂未检测到可归类的错误事件。",
        actions=[
            "如果你主观感受到延迟或卡顿，继续观察 media_stats、playback_mark_sent、playback_complete 的节奏。",
            "如果问题不可复现，保留这个 Call SID 作为对照样本。",
        ],
        evidence_events=reversed_events[:3],
    )
