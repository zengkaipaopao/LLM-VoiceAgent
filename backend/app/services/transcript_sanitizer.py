"""
Shared helpers for normalizing assistant transcript turns.
"""
from __future__ import annotations

import re
from typing import Optional

_ASSISTANT_PREFIX_PATTERN = re.compile(
    r"^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
    flags=re.IGNORECASE,
)
_ASSISTANT_INLINE_PREFIX_PATTERN = re.compile(
    r"(?im)(?:^|\n)\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*",
)
_INJECTED_USER_TURN_PATTERN = re.compile(
    r"(?im)(?:^|\n)\s*(?:user|customer|human|用户|お客様)\s*[:：]",
)


def find_injected_user_turn_start(text: str) -> Optional[int]:
    if not text:
        return None

    injected_turn = _INJECTED_USER_TURN_PATTERN.search(text)
    if not injected_turn:
        return None

    return injected_turn.start()


def sanitize_assistant_turn(text: str) -> str:
    if not text:
        return ""

    normalized = text.lstrip("\ufeff")
    normalized = _ASSISTANT_PREFIX_PATTERN.sub("", normalized, count=1)

    injected_turn_start = find_injected_user_turn_start(normalized)
    if injected_turn_start is not None:
        normalized = normalized[:injected_turn_start]

    normalized = _ASSISTANT_INLINE_PREFIX_PATTERN.sub("\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
