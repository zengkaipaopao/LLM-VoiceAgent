from __future__ import annotations

from app.schemas.prompts import PromptTemplate


def build_prompt_instructions(prompt: PromptTemplate) -> str:
    base_instructions = (prompt.system_prompt or "").strip()
    hints: list[str] = []

    voice_config = prompt.voice_config
    if voice_config and voice_config.voice:
        hints.append(f"If speech synthesis is used, always select the voice preset: {voice_config.voice}.")
    if voice_config and voice_config.speaking_rate is not None:
        hints.append(f"Maintain a speaking rate close to {voice_config.speaking_rate}x for clarity.")

    if prompt.capabilities.appointment_logging:
        hints.append(
            "[Appointment Logging Rules]\n"
            "- Only call logChatToSheet once all required fields (caller name, company, appointment, category, amount, address, extra request) have been explicitly confirmed.\n"
            "- If the user hangs up before all items are known, do not call the tool; continue guiding politely until everything is captured.\n"
            "- Wrap the payload in triple backticks and include: operation, timestamp (Japan ISO8601), caller_name, company, appointment, category, amount, address, summary, extra_request, raw_messages.\n"
            "- Capture extra_request verbatim; if the caller explicitly says they have none, store “なし”. Do not overwrite an earlier concrete request when they later say “特にありません”.\n"
            "- Acknowledge any additional request as soon as it is mentioned (“２台手配で承知しました”) before asking if anything else is required.\n"
            "- Generate timestamp using current Japan time (e.g., 2025-12-05T12:00:00+09:00) and write summary as one concise Japanese sentence.\n"
            "- Serialize rawMessages as a single string in the format {\"role\":\"user\",\"text\":\"...\",\"ts\":\"...\"}, {\"role\":\"assistant\",\"text\":\"...\",\"ts\":\"...\"}.\n"
            "- Keep the spoken channel silent while emitting the JSON block and avoid narration such as “内容をまとめます”."
        )

    if not hints:
        return base_instructions

    guidance = "\n".join(hints)
    if base_instructions:
        return f"{base_instructions}\n\n[Voice Guidance]\n{guidance}"
    return guidance
