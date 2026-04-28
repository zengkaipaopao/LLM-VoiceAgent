from datetime import datetime
from types import SimpleNamespace

from app.services.appointments.parsers import JapaneseAppointmentParser
from app.services.appointments.presenter import AppointmentBriefPresenter


def test_parser_extracts_spaced_voice_datetime_and_name():
    message = "会社 に 着く の は 、 ええ と 、 2026 年 の 5 月 1 日 の 11 時 、 田中 です 。"

    parsed = JapaneseAppointmentParser.extract_datetime_from_text(message)
    hints = JapaneseAppointmentParser.collect_operation_identity_hints(
        SimpleNamespace(caller_name="Test Caller", counterpart="chat_user"),
        message,
    )

    assert parsed == datetime(2026, 5, 1, 11, 0)
    assert hints["caller_name"] == "田中"
    assert hints["appointment_date"] == "2026-05-01"


def test_parser_resolves_amount_from_volume_fallback():
    amount = JapaneseAppointmentParser.resolve_amount({"estimated_volume_m3": 2.5})

    assert amount == "2.5 m3"


def test_presenter_formats_full_appointment_brief_with_fallbacks():
    appointment = SimpleNamespace(
        appointment=datetime(2026, 5, 1, 11, 0),
        caller_name="田中",
        company=None,
        category=None,
        amount=None,
        address="品川区1-2-3",
        extra_request="時間厳守",
        extracted_data={"waste_type": ["粗大ゴミ"], "estimated_volume_m3": 2.5},
    )

    summary = AppointmentBriefPresenter.format_appointment_brief(appointment)

    assert "予約日時: 2026-05-01 11:00" in summary
    assert "氏名: 田中" in summary
    assert "品目: 粗大ゴミ" in summary
    assert "重量・容量: 2.5m3" in summary
    assert "回収先住所: 品川区1-2-3" in summary
    assert "備考: 時間厳守" in summary

