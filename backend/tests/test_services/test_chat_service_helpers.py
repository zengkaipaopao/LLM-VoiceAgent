from types import SimpleNamespace

from app.services.chat_service import ChatService


def test_resolve_chat_response_mode_for_test_lab_forces_text():
    call = SimpleNamespace(extra_data={"source": "test_lab"})
    template = SimpleNamespace(response_format="json_object", output_schema={"type": "object"})

    response_format, output_schema = ChatService._resolve_chat_response_mode(call, template)

    assert response_format == "text"
    assert output_schema is None


def test_parse_messages_from_transcript_fallback():
    transcript = "用户: 你好\n助手: 你好，我是助手。\n\n用户: 你是谁\n助手: 我是预约助手。"

    messages = ChatService._parse_messages_from_transcript(transcript)

    assert messages == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，我是助手。"},
        {"role": "user", "content": "你是谁"},
        {"role": "assistant", "content": "我是预约助手。"},
    ]


def test_sanitize_assistant_response_prefix():
    assert ChatService._sanitize_assistant_response("Assistant: こんにちは") == "こんにちは"
    assert ChatService._sanitize_assistant_response("AI助手：您好") == "您好"
    assert ChatService._sanitize_assistant_response("助手: 测试") == "测试"


def test_normalize_messages_sanitizes_assistant_prefix():
    normalized = ChatService._normalize_messages(
        [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "Assistant: こんにちは"},
            {"role": "助手", "content": "Assistant: 承知しました"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert normalized == [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "こんにちは"},
        {"role": "assistant", "content": "承知しました"},
        {"role": "user", "content": "hello"},
    ]


def test_resolve_amount_fallback_from_summary_text():
    raw_data = {
        "estimated_volume_m3": None,
        "summary": "2026年4月22日に粗大ゴミ3kgの回収依頼。",
    }

    amount = ChatService._resolve_amount(raw_data)

    assert amount == "3kg"


def test_resolve_amount_handles_string_estimated_weight():
    raw_data = {
        "estimated_weight_kg": "3",
    }

    amount = ChatService._resolve_amount(raw_data)

    assert amount == "3 kg"


def test_resolve_amount_fallback_from_transcript_text():
    raw_data = {}
    transcript = "用户: 粗大ゴミ３kg\n助手: 承知しました。"

    amount = ChatService._resolve_amount(raw_data, transcript)

    assert amount == "３kg"


def test_resolve_amount_supports_ton_and_cubic_aliases():
    amount_ton = ChatService._resolve_amount({}, "重量は2tです。")
    amount_volume = ChatService._resolve_amount({}, "体積は8立方米です。")
    amount_short_volume = ChatService._resolve_amount({}, "体積は3立方です。")

    assert amount_ton == "2t"
    assert amount_volume == "8立方米"
    assert amount_short_volume == "3立方"


def test_resolve_amount_ignores_iso_datetime():
    amount = ChatService._resolve_amount({}, "2026-04-02T09:33:26+09:00")

    assert amount is None
