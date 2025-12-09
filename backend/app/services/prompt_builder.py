from __future__ import annotations

from app.schemas.prompts import PromptTemplate


def build_prompt_instructions(prompt: PromptTemplate) -> str:
    base_instructions = (prompt.system_prompt or '').strip()
    hints: list[str] = []

    welcome = (prompt.welcome_message or '').strip()
    if welcome:
        hints.append(f'When the session starts, greet the caller with: {welcome}')

    voice_config = prompt.voice_config
    if voice_config and voice_config.voice:
        hints.append(f'If speech synthesis is used, always select the voice preset: {voice_config.voice}.')
    if voice_config and voice_config.speaking_rate is not None:
        hints.append(f'Maintain a speaking rate close to {voice_config.speaking_rate}x for clarity.')

    if prompt.capabilities.appointment_logging:
        hints.append('Before confirming a reservation, explicitly ask: “追加依頼などのご要望はございますか？” to capture any extra requests.')
        hints.append(
            '[Appointment Logging Rules]\n'
            '- Only produce a JSON block after all of the following are confirmed: caller name, company, desired datetime, pickup category, quantity, address, and extra request.\n'
            '- The JSON must be wrapped with triple backticks and include: operation (create/update/delete), timestamp (Japan ISO-8601), caller_name, company, appointment, category, amount, address, summary, extra_request.\n'
            '- The extra_request field must capture the caller’s wording verbatim. If they explicitly say “no extra requests,” record the literal phrase “なし” (or “特にありません”) instead of leaving the field empty.\n'
            '- If the caller gives a concrete request and later says “nothing else,” keep the original request text (treat the later response as “no additional requests”).\n'
            '- Do NOT describe or announce the JSON (avoid phrases such as “内容をまとめます” or “以下の形式で”). Emit the code block immediately with no narration.\n'
            '- Keep the spoken channel silent while the JSON block is being output; the only spoken sentence after that must be the final confirmation.'
        )
        hints.append('Always end with the exact sentence “ご予約内容を受付いたしました。ご利用ありがとうございます。” and never mention internal processing, waiting, or summarizing transitions.')
        hints.append('Once the information is complete, output the JSON immediately followed by the closing sentence—do not say phrases like “少々お待ちください”, “記録を行います”, or “内容をまとめます”.')
        hints.append('Do not ask the caller to type instructions such as “受付完了”; you must finish autonomously once everything is confirmed.')

    if not hints:
        return base_instructions

    guidance = '\n'.join(hints)
    if base_instructions:
        return f"{base_instructions}\n\n[Voice Guidance]\n{guidance}"
    return guidance
