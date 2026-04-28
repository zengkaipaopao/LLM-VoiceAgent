"""Deterministic parsers for Japanese appointment conversations."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

from app.utils.datetime_utils import now_tokyo_naive, to_tokyo_naive


class JapaneseAppointmentParser:
    """Parse deterministic appointment signals from ASR/chat text."""

    AMOUNT_PATTERN = re.compile(
        r"([0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:kg|ｋｇ|キロ(?:グラム)?|g|ｇ|グラム|トン|ton(?:s)?|t(?![0-9０-９])|吨|噸|m[3３]|m³|㎥|立方メートル|立方米|立方|立米|袋|点|個|台|脚|本|箱|枚))",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def first_non_empty(*values: Any) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @classmethod
    def parse_appointment_time(cls, value: Optional[str]) -> datetime:
        if not value:
            return now_tokyo_naive()

        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return to_tokyo_naive(parsed) or now_tokyo_naive()

    @classmethod
    def parse_optional_appointment_time(cls, value: Any) -> Optional[datetime]:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None

        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            return to_tokyo_naive(parsed) or parsed
        except ValueError:
            return cls.extract_datetime_from_text(raw_value)

    @classmethod
    def extract_amount_from_text(cls, text: Optional[str]) -> Optional[str]:
        normalized = cls.first_non_empty(text)
        if not normalized:
            return None
        match = cls.AMOUNT_PATTERN.search(normalized)
        if not match:
            return None
        return match.group(1).strip()

    @classmethod
    def resolve_amount(cls, raw_data: dict[str, Any], *fallback_texts: Optional[str]) -> Optional[str]:
        numeric_pattern = r"[0-9０-９]+(?:[.,．][0-9０-９]+)?"

        def format_with_unit(value: Optional[str], unit: str) -> Optional[str]:
            if not value:
                return None
            if re.fullmatch(numeric_pattern, value):
                return f"{value} {unit}"
            return value

        direct_amount = cls.first_non_empty(
            raw_data.get("amount"),
            raw_data.get("quantity"),
            raw_data.get("volume"),
            raw_data.get("weight"),
        )
        if direct_amount:
            return direct_amount

        weight_kg = raw_data.get("estimated_weight_kg")
        if isinstance(weight_kg, (int, float)):
            value = int(weight_kg) if float(weight_kg).is_integer() else weight_kg
            return f"{value} kg"

        weight_text = cls.first_non_empty(raw_data.get("weight_kg"), raw_data.get("estimated_weight_kg"))
        if weight_text:
            return format_with_unit(weight_text, "kg")

        volume = raw_data.get("estimated_volume_m3")
        if isinstance(volume, (int, float)):
            value = int(volume) if float(volume).is_integer() else volume
            return f"{value} m3"

        volume_text = cls.first_non_empty(volume)
        if volume_text:
            return format_with_unit(volume_text, "m3")

        for candidate_text in (
            raw_data.get("summary"),
            raw_data.get("appointment_content"),
            raw_data.get("special_notes"),
            *fallback_texts,
        ):
            extracted = cls.extract_amount_from_text(cls.first_non_empty(candidate_text))
            if extracted:
                return extracted

        return None

    @classmethod
    def resolve_address(cls, raw_data: dict[str, Any]) -> Optional[str]:
        return cls.first_non_empty(
            raw_data.get("pickup_address"),
            raw_data.get("address"),
            raw_data.get("location"),
        )

    @classmethod
    def resolve_extra_request(cls, raw_data: dict[str, Any]) -> Optional[str]:
        special_notes = cls.first_non_empty(raw_data.get("special_notes"), raw_data.get("extra_request"))
        time_window = cls.first_non_empty(raw_data.get("preferred_time_window"))
        floor = cls.first_non_empty(raw_data.get("floor"))
        elevator = raw_data.get("elevator")

        fragments: list[str] = []
        if special_notes:
            fragments.append(f"備考: {special_notes}")
        if time_window:
            fragments.append(f"希望時間帯: {time_window}")
        if floor:
            fragments.append(f"階数: {floor}")
        if elevator is True:
            fragments.append("エレベーター: あり")
        elif elevator is False:
            fragments.append("エレベーター: なし")

        return " / ".join(fragments) if fragments else None

    @classmethod
    def resolve_category(cls, extraction_category: Optional[str], raw_data: dict[str, Any]) -> Optional[str]:
        direct = cls.first_non_empty(extraction_category, raw_data.get("category"))
        if direct:
            return direct

        waste_type = raw_data.get("waste_type")
        if isinstance(waste_type, list):
            items = [str(item).strip() for item in waste_type if str(item).strip()]
            if items:
                return "、".join(items)

        items = raw_data.get("items")
        if isinstance(items, list):
            item_names = [str(item).strip() for item in items if str(item).strip()]
            if item_names:
                return "、".join(item_names)

        return None

    @staticmethod
    def normalize_datetime_text(text: str) -> str:
        return re.sub(r"[\s　]+", "", text or "")

    @staticmethod
    def extract_operation_type_from_raw_data(raw_data: dict[str, Any]) -> Optional[str]:
        request_type = str(raw_data.get("request_type") or "").strip().lower()
        if request_type in {"cancel", "update"}:
            return request_type
        return None

    @staticmethod
    def is_cancelled_appointment(appointment: Any) -> bool:
        extra_data = appointment.extra_data if isinstance(appointment.extra_data, dict) else {}
        lifecycle_status = str(extra_data.get("lifecycle_status") or "").strip().lower()
        return lifecycle_status == "cancelled"

    @classmethod
    def build_update_changes_from_extraction(cls, raw_data: dict[str, Any]) -> dict[str, str]:
        change_set = raw_data.get("change_set")
        source = change_set if isinstance(change_set, dict) else raw_data
        changes: dict[str, str] = {}

        appointment_time = cls.first_non_empty(source.get("appointment_time"))
        if appointment_time:
            changes["appointment"] = appointment_time

        pickup_address = cls.first_non_empty(source.get("pickup_address"))
        if pickup_address:
            changes["address"] = pickup_address

        amount = cls.first_non_empty(source.get("amount"))
        if not amount and source.get("estimated_volume_m3") is not None:
            amount = f"{source.get('estimated_volume_m3')}m3"
        if amount:
            changes["amount"] = amount

        category = cls.resolve_category(cls.first_non_empty(source.get("category")), source)
        if category:
            changes["category"] = category

        return changes

    @classmethod
    def detect_operation_intent(cls, text: str) -> Optional[str]:
        normalized = text.strip().lower()
        if not normalized:
            return None

        cancel_keywords = [
            "キャンセル",
            "取消",
            "取り消",
            "中止",
            "cancel",
        ]
        update_keywords = [
            "変更",
            "修正",
            "更新",
            "変え",
            "改め",
            "reschedule",
            "update",
        ]

        if any(keyword in normalized for keyword in cancel_keywords):
            return "cancel"
        if any(keyword in normalized for keyword in update_keywords):
            return "update"
        return None

    @staticmethod
    def normalize_identity_token(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = value.strip().lower()
        return re.sub(r"[\s_\-]+", "", normalized)

    @classmethod
    def is_generic_caller_name(cls, value: Optional[str]) -> bool:
        normalized = cls.normalize_identity_token(value)
        generic_tokens = {
            "",
            "testcaller",
            "testuser",
            "chatuser",
            "caller",
            "unknown",
            "guest",
            "visitor",
            "anonymous",
            "anon",
            "お客様",
            "顧客",
            "利用者",
            "テスト",
            "テストユーザー",
            "テスト利用者",
        }
        return normalized in generic_tokens

    @classmethod
    def is_placeholder_counterpart(cls, value: Optional[str]) -> bool:
        normalized = cls.normalize_identity_token(value)
        placeholder_tokens = {
            "",
            "chatuser",
            "testuser",
            "unknown",
            "anonymous",
            "guest",
            "visitor",
            "none",
            "null",
            "-",
        }
        return normalized in placeholder_tokens

    @staticmethod
    def is_affirmative(text: str) -> bool:
        normalized = text.strip().lower()
        positives = [
            "はい",
            "ええ",
            "yes",
            "ok",
            "okay",
            "是",
            "好的",
            "没问题",
            "それで大丈夫",
            "お願いします",
        ]
        return any(token in normalized for token in positives)

    @staticmethod
    def is_negative(text: str) -> bool:
        normalized = text.strip().lower()
        negatives = [
            "いいえ",
            "違います",
            "違う",
            "no",
            "不是",
            "不对",
            "やめ",
        ]
        return any(token in normalized for token in negatives)

    @classmethod
    def extract_target_date(cls, text: str) -> Optional[date]:
        if not text:
            return None

        normalized_text = cls.normalize_datetime_text(text)
        patterns = [
            r"(\d{4})(?:[/-]|年(?:の)?)(\d{1,2})(?:[/-]|月(?:の)?)(\d{1,2})(?:日)?",
            r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized_text)
            if not match:
                continue
            try:
                year, month, day = (int(part) for part in match.groups())
                return date(year, month, day)
            except ValueError:
                continue
        return None

    @classmethod
    def extract_datetime_parts_from_text(cls, text: str) -> tuple[Optional[datetime], bool]:
        if not text:
            return None, False

        normalized_text = cls.normalize_datetime_text(text)
        match = re.search(
            r"(\d{4})(?:[/-]|年(?:の)?)(\d{1,2})(?:[/-]|月(?:の)?)(\d{1,2})(?:日)?(?:[^\d]{0,8}(\d{1,2})(?::|時)(\d{1,2})?(?:分)?)?",
            normalized_text,
        )
        if not match:
            return None, False

        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        has_time = bool(match.group(4))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        try:
            return datetime(year, month, day, hour, minute), has_time
        except ValueError:
            return None, False

    @classmethod
    def extract_datetime_from_text(cls, text: str) -> Optional[datetime]:
        parsed, _ = cls.extract_datetime_parts_from_text(text)
        return parsed

    @staticmethod
    def extract_address_from_text(text: str) -> Optional[str]:
        if not text:
            return None

        patterns = [
            r"(?:住所|地址|回収先|pickup\s*address)\s*(?:は|为|:|：)?\s*(.+)",
            r"(東京都|北海道|(?:京都|大阪)府|.{2,3}県.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip("。 　")
            if candidate:
                return candidate
        return None

    @classmethod
    def extract_update_changes(cls, text: str) -> dict[str, str]:
        changes: dict[str, str] = {}

        appointment_dt = cls.extract_datetime_from_text(text)
        if appointment_dt:
            changes["appointment"] = appointment_dt.isoformat()

        amount = cls.extract_amount_from_text(text)
        if amount:
            changes["amount"] = amount

        address = cls.extract_address_from_text(text)
        if address:
            changes["address"] = address

        category_match = re.search(r"(?:品目|種類|类别|category)\s*(?:は|为|:|：)?\s*([^\n。]+)", text, flags=re.IGNORECASE)
        if category_match:
            category = category_match.group(1).strip()
            if category:
                changes["category"] = category

        return changes

    @staticmethod
    def normalize_phone_number(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"\D+", "", value)

    @staticmethod
    def normalize_match_text(value: Optional[str]) -> str:
        if not value:
            return ""
        lowered = value.strip().lower()
        return re.sub(r"[\s　]+", "", lowered)

    @classmethod
    def loosely_matches(cls, left: Optional[str], right: Optional[str]) -> bool:
        left_norm = cls.normalize_match_text(left)
        right_norm = cls.normalize_match_text(right)
        if not left_norm or not right_norm:
            return False
        return left_norm in right_norm or right_norm in left_norm

    @classmethod
    def extract_company_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        patterns = [
            r"(?:会社名|会社|company|公司)\s*(?:は|:|：)?\s*([^\n。]{1,80})",
            r"([^\s、。]{1,80}会社)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip(" 　。")
            candidate = re.split(
                r"(?:予約日|回収希望日|電話番号|連絡先|氏名|名前|担当者|,|，|、)",
                candidate,
                maxsplit=1,
            )[0].strip(" 　。")
            if candidate:
                return candidate
        return None

    @classmethod
    def extract_company_hint_from_expected_reply(cls, text: str) -> Optional[str]:
        if not text:
            return None

        normalized = text.strip()
        if not normalized:
            return None

        if re.fullmatch(r"個人(?:です|でお願いします|でございます)?[。]?", normalized):
            return "個人"

        cleaned = re.sub(r"(?:です|でございます|でお願いします)$", "", normalized).strip(" 　。")
        if not cleaned:
            return None

        invalid_tokens = {
            "はい",
            "いいえ",
            "お願いします",
            "変更",
            "キャンセル",
            "予約",
            "回収",
            "住所",
            "日時",
            "電話番号",
            "連絡先",
        }
        if cleaned in invalid_tokens:
            return None
        if re.search(r"[?？]", cleaned):
            return None

        return cleaned

    @classmethod
    def extract_name_hint_from_expected_reply(cls, text: str) -> Optional[str]:
        if not text:
            return None

        normalized = text.strip()
        if not normalized:
            return None

        cleaned = re.sub(r"(?:です|と申します|でございます)$", "", normalized).strip(" 　。")
        if not cleaned:
            return None

        if (
            cls.is_generic_caller_name(cleaned)
            or "会社" in cleaned
            or "会社の" in cleaned
            or re.search(r"[?？]", cleaned)
        ):
            return None
        return cleaned

    @classmethod
    def extract_company_name_pair(cls, text: str) -> tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None

        match = re.search(
            r"([^\s、。]{1,80}会社)\s*の\s*([^\s、。]{1,40})(?:です|と申します|でございます)?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, None

        company = match.group(1).strip(" 　。")
        caller_name = match.group(2).strip(" 　。")
        caller_name = re.sub(r"(?:です|と申します|でございます)$", "", caller_name).strip(" 　。")
        if cls.is_generic_caller_name(caller_name):
            caller_name = None
        return company or None, caller_name or None

    @classmethod
    def extract_name_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        compact_text = re.sub(r"[\s　]+", "", text)
        patterns = [
            r"(?:お名前|名前|氏名|担当者(?:名)?|依頼者)\s*(?:は|:|：)?\s*([^\n、。]{1,60})",
            r"([^\s、。]{1,40})と申します",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1).strip(" 　。")
            if (
                candidate
                and not cls.is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
            ):
                return candidate

        trailing_intro = re.search(
            r"(?:^|[、,。])([^、,。]{1,32})(?:です|と申します|でございます)(?:[。.]|$)",
            compact_text,
        )
        if trailing_intro:
            candidate = trailing_intro.group(1).strip(" 　。")
            invalid_fragments = [
                "予約",
                "変更",
                "キャンセル",
                "予定",
                "回収",
                "したい",
                "希望",
                "お願い",
                "はい",
                "いいえ",
            ]
            if (
                candidate
                and not cls.is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
                and not any(fragment in candidate for fragment in invalid_fragments)
            ):
                return candidate

        short_self_intro = re.fullmatch(r"\s*([^\s、。]{1,32})\s*です\s*[。]?\s*", text)
        if short_self_intro:
            candidate = short_self_intro.group(1).strip(" 　。")
            invalid_fragments = [
                "予約",
                "変更",
                "キャンセル",
                "予定",
                "回収",
                "したい",
                "希望",
                "お願い",
                "です",
            ]
            if (
                candidate
                and not cls.is_generic_caller_name(candidate)
                and "会社" not in candidate
                and "会社の" not in candidate
                and not any(fragment in candidate for fragment in invalid_fragments)
            ):
                return candidate
        return None

    @classmethod
    def extract_phone_hint(cls, text: str) -> Optional[str]:
        if not text:
            return None

        match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
        if not match:
            return None

        candidate = match.group(1).strip()
        normalized = cls.normalize_phone_number(candidate)
        if len(normalized) < 9:
            return None
        return candidate

    @classmethod
    def collect_operation_identity_hints(
        cls,
        call: Any,
        user_message: str,
        *,
        base_hints: Optional[dict[str, str]] = None,
        expected_identity_key: Optional[str] = None,
    ) -> dict[str, str]:
        hints: dict[str, str] = dict(base_hints or {})

        message_company, message_caller_name = cls.extract_company_name_pair(user_message)

        caller_name = cls.first_non_empty(message_caller_name, cls.extract_name_hint(user_message))
        if not caller_name:
            caller_name = cls.first_non_empty(hints.get("caller_name"))
        if not caller_name:
            call_name = cls.first_non_empty(getattr(call, "caller_name", None))
            if call_name and not cls.is_generic_caller_name(call_name):
                caller_name = call_name
        if caller_name and not cls.is_generic_caller_name(caller_name):
            hints["caller_name"] = caller_name
        else:
            hints.pop("caller_name", None)

        company = cls.first_non_empty(message_company, cls.extract_company_hint(user_message))
        if not company and expected_identity_key == "company":
            company = cls.extract_company_hint_from_expected_reply(user_message)
        if not company:
            company = cls.first_non_empty(hints.get("company"))
        if company:
            hints["company"] = company
        else:
            hints.pop("company", None)

        counterpart = cls.extract_phone_hint(user_message)
        if not counterpart:
            counterpart = cls.first_non_empty(hints.get("counterpart"))
        if not counterpart:
            call_counterpart = cls.first_non_empty(getattr(call, "counterpart", None))
            if call_counterpart and not cls.is_placeholder_counterpart(call_counterpart):
                counterpart = call_counterpart
        if counterpart and not cls.is_placeholder_counterpart(counterpart):
            hints["counterpart"] = counterpart
        else:
            hints.pop("counterpart", None)

        appointment_date = cls.extract_target_date(user_message)
        if not appointment_date and expected_identity_key == "appointment_date":
            appointment_date = cls.extract_target_date(f"{now_tokyo_naive().year}年{user_message}")
        if appointment_date:
            hints["appointment_date"] = appointment_date.isoformat()
        else:
            existing_date = cls.parse_hint_date(hints)
            if existing_date:
                hints["appointment_date"] = existing_date.isoformat()
            else:
                hints.pop("appointment_date", None)

        if expected_identity_key == "caller_name" and "caller_name" not in hints:
            fallback_name = cls.extract_name_hint_from_expected_reply(user_message)
            if fallback_name:
                hints["caller_name"] = fallback_name

        return hints

    @staticmethod
    def count_operation_identity_hints(hints: dict[str, str]) -> int:
        keys = ("caller_name", "company", "counterpart", "appointment_date")
        return sum(1 for key in keys if str(hints.get(key) or "").strip())

    @staticmethod
    def parse_hint_date(hints: dict[str, str]) -> Optional[date]:
        raw_value = str(hints.get("appointment_date") or "").strip()
        if not raw_value:
            return None
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            return None

    @classmethod
    def score_operation_candidate(
        cls,
        appointment: Any,
        related_call: Optional[Any],
        hints: dict[str, str],
    ) -> int:
        matched_keys: set[str] = set()

        hint_name = hints.get("caller_name")
        if hint_name and (
            cls.loosely_matches(hint_name, appointment.caller_name)
            or cls.loosely_matches(hint_name, getattr(related_call, "caller_name", None))
        ):
            matched_keys.add("caller_name")

        hint_company = hints.get("company")
        if hint_company and cls.loosely_matches(hint_company, appointment.company):
            matched_keys.add("company")

        hint_phone = cls.normalize_phone_number(hints.get("counterpart"))
        candidate_phone = cls.normalize_phone_number(getattr(related_call, "counterpart", None))
        if hint_phone and candidate_phone:
            shorter, longer = sorted([hint_phone, candidate_phone], key=len)
            if hint_phone == candidate_phone or (len(shorter) >= 8 and longer.endswith(shorter)):
                matched_keys.add("counterpart")

        hint_date = cls.parse_hint_date(hints)
        if hint_date and isinstance(appointment.appointment, datetime) and appointment.appointment.date() == hint_date:
            matched_keys.add("appointment_date")

        return len(matched_keys)

    @classmethod
    def score_extracted_operation_candidate(
        cls,
        appointment: Any,
        related_call: Optional[Any],
        *,
        raw_data: dict[str, Any],
        target_time: Optional[datetime],
    ) -> int:
        score = 0

        if target_time and isinstance(appointment.appointment, datetime):
            if appointment.appointment.date() != target_time.date():
                return 0
            score += 2
            if (
                appointment.appointment.hour == target_time.hour
                and appointment.appointment.minute == target_time.minute
            ):
                score += 2

        caller_name = cls.first_non_empty(raw_data.get("caller_name"))
        if caller_name and (
            cls.loosely_matches(caller_name, appointment.caller_name)
            or cls.loosely_matches(caller_name, getattr(related_call, "caller_name", None))
        ):
            score += 2

        company = cls.first_non_empty(raw_data.get("company"))
        if company and cls.loosely_matches(company, appointment.company):
            score += 1

        pickup_address = cls.first_non_empty(raw_data.get("pickup_address"))
        if pickup_address and cls.loosely_matches(pickup_address, appointment.address):
            score += 1

        contact_phone = cls.normalize_phone_number(cls.first_non_empty(raw_data.get("contact_phone")))
        candidate_phone = cls.normalize_phone_number(getattr(related_call, "counterpart", None))
        if contact_phone and candidate_phone:
            shorter, longer = sorted([contact_phone, candidate_phone], key=len)
            if contact_phone == candidate_phone or (len(shorter) >= 8 and longer.endswith(shorter)):
                score += 1

        return score

    @classmethod
    def next_identity_question_key(cls, hints: dict[str, str], *, no_match: bool = False) -> str:
        collect_order = ("caller_name", "company", "appointment_date", "counterpart")
        verify_order = ("appointment_date", "caller_name", "company", "counterpart")
        order = verify_order if no_match else collect_order
        for key in order:
            if not str(hints.get(key) or "").strip():
                return key
        return order[0]

    @classmethod
    def build_identity_single_question(cls, key: str) -> str:
        prompts = {
            "caller_name": "ご予約者様のお名前を教えてください。",
            "company": "会社名を教えてください。個人の場合は「個人」で問題ありません。",
            "counterpart": "ご連絡先の電話番号を教えてください。",
            "appointment_date": "回収希望日を教えてください。（例: 2026年4月1日）",
        }
        return prompts.get(key, "確認のため、予約情報をもう一度教えてください。")

    @classmethod
    def build_operation_identity_prompt(
        cls,
        hints: dict[str, str],
        *,
        no_match: bool = False,
        mismatch_count: int = 0,
    ) -> str:
        next_key = cls.next_identity_question_key(hints, no_match=no_match)
        question = cls.build_identity_single_question(next_key)
        known_count = cls.count_operation_identity_hints(hints)

        if no_match and mismatch_count >= 2:
            return (
                "ありがとうございます。現在の情報では対象予約を特定できませんでした。"
                f" {question}"
            )
        if no_match:
            return f"ありがとうございます。現在の情報では対象予約を特定できませんでした。確認のため、{question}"
        if known_count == 0:
            return f"予約変更・キャンセル対象を確認します。まず、{question}"
        return f"ありがとうございます。続けて、{question}"

