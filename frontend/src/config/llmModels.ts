export const DEFAULT_GENERATE_MODEL = 'gemini-2.5-flash';
export const DEFAULT_LIVE_MODEL = 'gemini-2.5-flash-native-audio-latest';

export function isLiveModelId(model: string | null | undefined): boolean {
  const token = (model ?? '').trim().toLowerCase();
  if (!token) {
    return false;
  }
  return token.includes('live') || token.includes('realtime') || token.includes('native-audio');
}

export function describeTextTabModelWarning(
  model: string | null | undefined,
  promptCode?: string | null
): string | null {
  const token = (model ?? '').trim();
  if (!token || !isLiveModelId(token)) {
    return null;
  }

  const promptLabel = (promptCode ?? '').trim() ? `当前 Prompt（${promptCode?.trim()}）` : '当前 Prompt';
  return `${promptLabel} 配置的是语音模型 ${token}。文字测试无法使用该模型，请切换到语音测试，或把 Prompt 模型改成可用于文本生成的模型。`;
}

export function describeVoiceTabPromptModelWarning(
  model: string | null | undefined,
  promptCode?: string | null
): string | null {
  const token = (model ?? '').trim();
  if (!token || isLiveModelId(token)) {
    return null;
  }

  const promptLabel = (promptCode ?? '').trim() ? `当前 Prompt（${promptCode?.trim()}）` : '当前 Prompt';
  return `${promptLabel} 配置的是文字模型 ${token}。语音测试需要 Gemini Live / Native Audio 模型；请修改 Prompt 模型，或在“Gemini Live 模型”输入框里手动覆盖。`;
}

export function describeVoiceTabOverrideWarning(model: string | null | undefined): string | null {
  const token = (model ?? '').trim();
  if (!token || isLiveModelId(token)) {
    return null;
  }

  return `当前语音会话模型 ${token} 不是 Gemini Live / Native Audio 模型。连接前请改成语音模型，或重新选择一个使用语音模型的 Prompt。`;
}

export function describeTwilioTabPromptModelWarning(
  model: string | null | undefined,
  promptCode?: string | null
): string | null {
  const token = (model ?? '').trim();
  if (!token || !isLiveModelId(token)) {
    return null;
  }

  const promptLabel = (promptCode ?? '').trim() ? `当前 Prompt（${promptCode?.trim()}）` : '当前 Prompt';
  return `${promptLabel} 配置的是语音模型 ${token}。Twilio ConversationRelay 按官方方式接收文字 token 并由 Twilio 负责电话语音层，因此这里需要可用于文本生成的模型；请把 Prompt 模型改成 generate 模型后再测试电话网关。`;
}
