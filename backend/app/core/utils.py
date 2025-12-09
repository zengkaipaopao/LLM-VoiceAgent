from __future__ import annotations


def split_models(config_value: str | None) -> list[str]:
    """Split comma-separated model IDs into a unique, trimmed list."""
    if not config_value:
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in config_value.split(","):
        value = raw.strip()
        if value and value not in seen:
            cleaned.append(value)
            seen.add(value)
    return cleaned
