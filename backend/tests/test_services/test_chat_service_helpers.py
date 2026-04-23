from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

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


def test_sanitize_assistant_response_truncates_injected_user_turn():
    raw = (
        "ご依頼内容を確認しました。\n\n"
        "User: はい\n\n"
        "Assistant: 依頼内容を承りました。"
    )
    assert ChatService._sanitize_assistant_response(raw) == "ご依頼内容を確認しました。"


def test_sanitize_assistant_response_removes_inline_assistant_prefix():
    raw = (
        "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。\n\n"
        "Assistant: 2026年4月1日の粗大ゴミ回収のご希望ですね。新規予約ということで承ってよろしいでしょうか？"
    )
    sanitized = ChatService._sanitize_assistant_response(raw)
    assert "Assistant:" not in sanitized
    assert "新規予約ということで承ってよろしいでしょうか？" in sanitized


def test_strip_redundant_opening_greeting_after_first_turn():
    raw = (
        "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
        "\n\n粗大ゴミの回収をご希望とのこと、承知いたしました。"
    )
    cleaned = ChatService._strip_redundant_opening_greeting(
        raw,
        prior_assistant_messages=[
            "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
        ],
    )
    assert cleaned == "粗大ゴミの回収をご希望とのこと、承知いたしました。"


def test_strip_redundant_opening_greeting_keeps_first_turn():
    raw = "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
    cleaned = ChatService._strip_redundant_opening_greeting(raw, prior_assistant_messages=[])
    assert cleaned == raw


def test_strip_redundant_opening_greeting_uses_prior_message_leading_sentence():
    prior = ["こんにちは。廃棄物回収受付です。ご用件をお伺いします。"]
    raw = "こんにちは。廃棄物回収受付です。ご用件をお伺いします。\n次に回収先住所を教えてください。"

    cleaned = ChatService._strip_redundant_opening_greeting(raw, prior_assistant_messages=prior)

    assert cleaned == "次に回収先住所を教えてください。"


def test_find_injected_user_turn_start():
    text = "ご案内します。\n\nUser: はい"
    start = ChatService._find_injected_user_turn_start(text)
    assert start is not None
    assert text[start:].startswith("\n\nUser:")


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


def test_detect_operation_intent_update_and_cancel():
    assert ChatService._detect_operation_intent("预约を変更したいです") == "update"
    assert ChatService._detect_operation_intent("この予約をキャンセルしてください") == "cancel"
    assert ChatService._detect_operation_intent("新規予約をしたいです") is None


def test_generic_identity_detection():
    assert ChatService._is_generic_caller_name("Test Caller")
    assert ChatService._is_generic_caller_name("chat_user")
    assert ChatService._is_placeholder_counterpart("chat_user")
    assert ChatService._is_placeholder_counterpart("UNKNOWN")
    assert not ChatService._is_generic_caller_name("山田太郎")
    assert not ChatService._is_placeholder_counterpart("+819012345678")


def test_extract_company_name_pair_from_natural_sentence():
    company, caller_name = ChatService._extract_company_name_pair("ABC会社のCCCです。")
    assert company == "ABC会社"
    assert caller_name == "CCC"


def test_collect_operation_identity_hints_expected_company_accepts_short_reply():
    call = SimpleNamespace(caller_name="Test Caller", counterpart="chat_user")
    hints = ChatService._collect_operation_identity_hints(
        call,
        "ABC",
        base_hints={"caller_name": "CCC"},
        expected_identity_key="company",
    )
    assert hints.get("company") == "ABC"
    assert hints.get("caller_name") == "CCC"


def test_collect_operation_identity_hints_expected_company_accepts_individual():
    call = SimpleNamespace(caller_name="Test Caller", counterpart="chat_user")
    hints = ChatService._collect_operation_identity_hints(
        call,
        "個人です",
        base_hints={"caller_name": "CCC"},
        expected_identity_key="company",
    )
    assert hints.get("company") == "個人"


def test_collect_operation_identity_hints_expected_name_accepts_short_reply():
    call = SimpleNamespace(caller_name="Test Caller", counterpart="chat_user")
    hints = ChatService._collect_operation_identity_hints(
        call,
        "山田",
        base_hints={},
        expected_identity_key="caller_name",
    )
    assert hints.get("caller_name") == "山田"


def test_build_operation_identity_prompt_single_step():
    prompt = ChatService._build_operation_identity_prompt({"caller_name": "CCC", "counterpart": "+8190xxxx"})
    assert "続けて" in prompt
    assert "会社名" in prompt
    assert "回収希望日" not in prompt


def test_build_operation_identity_prompt_no_match_does_not_mention_reservation_id():
    prompt = ChatService._build_operation_identity_prompt(
        {"caller_name": "CCC", "company": "ABC会社", "appointment_date": "2026-04-01"},
        no_match=True,
        mismatch_count=2,
    )
    assert "予約ID" not in prompt


def test_format_appointment_brief_hides_internal_id():
    appointment = SimpleNamespace(
        id="dfc312e2-408e-46ef-948c-de5072b2b109",
        appointment=datetime(2026, 4, 10, 0, 0),
        caller_name="CCC",
        company="ABC会社",
        amount="2立方米",
        address="東京都千代田区神田2-4-33",
    )

    summary = ChatService._format_appointment_brief(appointment)

    assert "ID:" not in summary
    assert "予約日時:" in summary
    assert "CCC" in summary


def test_extract_datetime_from_text():
    parsed = ChatService._extract_datetime_from_text("日時を2026年4月10日10:30に変更したいです")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 4
    assert parsed.day == 10
    assert parsed.hour == 10
    assert parsed.minute == 30


def test_select_candidate_id_from_text():
    candidate_ids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]

    assert ChatService._select_candidate_id_from_text("2", candidate_ids) == candidate_ids[1]
    assert (
        ChatService._select_candidate_id_from_text(candidate_ids[0], candidate_ids)
        == candidate_ids[0]
    )


@pytest.mark.asyncio
async def test_find_operation_candidates_without_identity_returns_empty():
    service = ChatService.__new__(ChatService)
    repo = SimpleNamespace(search_operation_candidates=AsyncMock(return_value=[SimpleNamespace(id="x")]))
    repo.search_operation_candidates_with_call = AsyncMock(return_value=[])
    service.appointment_repo = repo

    call = SimpleNamespace(caller_name="Test Caller", counterpart="chat_user")
    candidates, hints = await service._find_operation_candidates(call, "こないだの予定を変更したいです")

    assert candidates == []
    assert hints == {}
    repo.search_operation_candidates_with_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_operation_candidates_prefers_counterpart_when_name_is_generic():
    service = ChatService.__new__(ChatService)
    expected = [
        SimpleNamespace(
            id="a",
            caller_name="任意",
            company="ABC会社",
            appointment=datetime(2026, 4, 1, 10, 0),
            timestamp=datetime(2026, 4, 2, 9, 0),
        )
    ]
    repo = SimpleNamespace(
        search_operation_candidates=AsyncMock(return_value=expected),
        search_operation_candidates_with_call=AsyncMock(
            return_value=[(expected[0], SimpleNamespace(counterpart="+819012345678", caller_name=None))]
        ),
    )
    service.appointment_repo = repo

    call = SimpleNamespace(caller_name="Test Caller", counterpart="+819012345678", id="call-id")
    candidates, hints = await service._find_operation_candidates(call, "会社名: ABC会社 予約日: 2026-04-01")

    assert candidates == expected
    assert hints["counterpart"] == "+819012345678"
    assert hints["company"] == "ABC会社"
    assert hints["appointment_date"] == "2026-04-01"
    assert repo.search_operation_candidates_with_call.await_count == 1
    kwargs = repo.search_operation_candidates_with_call.await_args.kwargs
    assert kwargs["caller_name"] is None
    assert kwargs["counterpart"] == "+819012345678"


@pytest.mark.asyncio
async def test_process_test_session_operation_turn_persists_handled_turn():
    call_id = uuid4()
    call = SimpleNamespace(id=call_id, extra_data={}, transcript="")
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        setup_chat_context=AsyncMock(
            return_value={
                "messages": [{"role": "assistant", "content": "前回の返答"}],
                "template": SimpleNamespace(),
                "system_prompt": "",
                "template_code": "base_appointment",
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            }
        ),
        persist_turn=AsyncMock(),
    )

    async def handle_flow(target_call, user_message):
        assert target_call is call
        assert user_message == "この予約をキャンセルしてください"
        target_call.extra_data = {
            "appointment_operation_flow": {
                "status": "await_target_confirmation",
                "operation": "cancel",
            }
        }
        return "キャンセル対象を確認しました。"

    service = ChatService.__new__(ChatService)
    service._build_chat_runtime_service = lambda: runtime
    service._handle_appointment_operation_flow = handle_flow
    service._sanitize_assistant_response = lambda value: value
    service._strip_redundant_opening_greeting = lambda value, prior_assistant_messages: value

    result = await service.process_test_session_operation_turn(
        call_id=call_id,
        message="この予約をキャンセルしてください",
        template_code="base_appointment",
    )

    assert result.handled is True
    assert result.response == "キャンセル対象を確認しました。"
    assert result.operation == "cancel"
    assert result.state_status == "await_target_confirmation"
    assert result.executed is False
    runtime.persist_turn.assert_awaited_once()
    persisted = runtime.persist_turn.await_args.kwargs
    assert persisted["user_message"] == "この予約をキャンセルしてください"
    assert persisted["assistant_message"] == "キャンセル対象を確認しました。"
    assert persisted["messages"][-2:] == [
        {"role": "user", "content": "この予約をキャンセルしてください"},
        {"role": "assistant", "content": "キャンセル対象を確認しました。"},
    ]


@pytest.mark.asyncio
async def test_process_test_session_operation_turn_skips_persist_when_not_handled():
    call_id = uuid4()
    call = SimpleNamespace(id=call_id, extra_data={}, transcript="")
    runtime = SimpleNamespace(
        get_or_create_call=AsyncMock(return_value=call),
        setup_chat_context=AsyncMock(
            return_value={
                "messages": [],
                "template": SimpleNamespace(),
                "system_prompt": "",
                "template_code": "base_appointment",
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash",
            }
        ),
        persist_turn=AsyncMock(),
    )

    service = ChatService.__new__(ChatService)
    service._build_chat_runtime_service = lambda: runtime
    service._handle_appointment_operation_flow = AsyncMock(return_value=None)
    service._sanitize_assistant_response = lambda value: value
    service._strip_redundant_opening_greeting = lambda value, prior_assistant_messages: value

    result = await service.process_test_session_operation_turn(
        call_id=call_id,
        message="新規予約をしたいです",
        template_code="base_appointment",
    )

    assert result.handled is False
    assert result.response is None
    assert result.executed is False
    runtime.persist_turn.assert_not_awaited()
