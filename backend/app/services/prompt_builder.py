from __future__ import annotations

from app.schemas.prompts import PromptTemplate


def build_prompt_instructions(prompt: PromptTemplate) -> str:
    base_instructions = (prompt.system_prompt or '').strip()
    hints: list[str] = []

    welcome = (prompt.welcome_message or '').strip()
    if welcome:
        hints.append(f'会话建立后请率先播报以下欢迎语：{welcome}')

    voice_config = prompt.voice_config
    if voice_config and voice_config.voice:
        hints.append(f'如需语音输出，请匹配 OpenAI 声音预设：{voice_config.voice}。')
    if voice_config and voice_config.speaking_rate is not None:
        hints.append(f'请保持语速约为 {voice_config.speaking_rate} 倍，兼顾清晰与自然。')

    if prompt.capabilities.appointment_logging:
        hints.append('在正式确认预约前，请主动询问一句：“追加依頼などのご要望はございますか？”，以确认是否存在补充需求。')
        hints.append(
            '[预约记录输出规则]\n'
            '- 仅在收集完整的联系人 / 公司 / 希望日期时间 / 回收类型 / 量 / 地址 / 追加要望后，才可输出 JSON。\n'
            '- JSON 需使用三个反引号包裹，字段包含：operation（create=新規 / update=変更 / delete=取消）、timestamp（日本时间 ISO8601）、caller_name、company、appointment、category、amount、address、summary。\n'
            '- JSON 中需包含 extra_request 字段，写入客户追加要望（如无则不要输出 JSON）。\n'
            '- JSON 输出后，再用自然语言告知用户“已记录完毕”。'
        )
        hints.append('结束语需固定为：“ご予約内容を受付いたしました。ご利用ありがとうございます。”，且不得添加“少々お待ちください”等等待提示或透露内部处理流程。')
        hints.append('当信息齐全准备输出 JSON 时，直接输出 JSON 与结束语，禁止在对话中说“少々お待ちください”或“记录を行います”等等待提示。')
        hints.append('请勿要求客户输入“受付完了”等指令，信息齐全后由你直接输出 JSON 与结束语。')

    if not hints:
        return base_instructions

    guidance = '\n'.join(hints)
    if base_instructions:
        return f"{base_instructions}\n\n[语音指引]\n{guidance}"
    return guidance
