from app.services.llm.gemini_service import GeminiService


def _contains_key(node, target_key: str) -> bool:
    if isinstance(node, dict):
        if target_key in node:
            return True
        return any(_contains_key(value, target_key) for value in node.values())
    if isinstance(node, list):
        return any(_contains_key(item, target_key) for item in node)
    return False


def test_normalize_schema_for_gemini_drops_additional_properties():
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "raw_data": {
                "type": "object",
                "additional_properties": {"type": "string"},
            },
        },
        "additional_properties": False,
    }

    normalized = GeminiService._normalize_schema_for_gemini(schema)

    assert normalized is not None
    assert not _contains_key(normalized, "additional_properties")
    assert not _contains_key(normalized, "additionalProperties")
