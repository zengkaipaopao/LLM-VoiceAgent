export const DEFAULT_GENERATE_MODEL = 'gemini-2.5-flash';
export const DEFAULT_LIVE_MODEL = 'gemini-2.5-flash-native-audio-latest';

interface ModelWarningTranslateOptions {
  defaultValue: string;
  [key: string]: unknown;
}

type ModelWarningTranslator = (key: string, options: ModelWarningTranslateOptions) => string;

export function isLiveModelId(model: string | null | undefined): boolean {
  const token = (model ?? '').trim().toLowerCase();
  if (!token) {
    return false;
  }
  return token.includes('live') || token.includes('realtime') || token.includes('native-audio');
}

function resolvePromptLabel(
  promptCode: string | null | undefined,
  translate?: ModelWarningTranslator
): string {
  const trimmedPromptCode = (promptCode ?? '').trim();
  if (!translate) {
    return trimmedPromptCode ? `当前 Prompt（${trimmedPromptCode}）` : '当前 Prompt';
  }
  if (trimmedPromptCode) {
    return translate('pages:test.modelWarnings.currentPromptWithCode', {
      defaultValue: 'Current prompt ({{promptCode}})',
      promptCode: trimmedPromptCode,
    });
  }
  return translate('pages:test.modelWarnings.currentPrompt', {
    defaultValue: 'Current prompt',
  });
}

export function describeTextTabModelWarning(
  model: string | null | undefined,
  promptCode?: string | null,
  translate?: ModelWarningTranslator
): string | null {
  const token = (model ?? '').trim();
  if (!token || !isLiveModelId(token)) {
    return null;
  }

  const promptLabel = resolvePromptLabel(promptCode, translate);
  if (translate) {
    return translate('pages:test.modelWarnings.textPromptUsesVoiceModel', {
      defaultValue:
        '{{promptLabel}} is configured with voice model {{modelId}}. Text testing cannot use this model. Switch to voice testing or change the prompt model to a text generation model.',
      promptLabel,
      modelId: token,
    });
  }
  return `${promptLabel} 配置的是语音模型 ${token}。文字测试无法使用该模型，请切换到语音测试，或把 Prompt 模型改成可用于文本生成的模型。`;
}

export function describeVoiceTabPromptModelWarning(
  model: string | null | undefined,
  promptCode?: string | null,
  translate?: ModelWarningTranslator
): string | null {
  const token = (model ?? '').trim();
  if (!token || isLiveModelId(token)) {
    return null;
  }

  const promptLabel = resolvePromptLabel(promptCode, translate);
  if (translate) {
    return translate('pages:test.modelWarnings.voicePromptUsesTextModel', {
      defaultValue:
        '{{promptLabel}} is configured with text model {{modelId}}. Voice testing requires a Gemini Live / Native Audio model. Update the prompt model or override it in the Gemini Live model field.',
      promptLabel,
      modelId: token,
    });
  }
  return `${promptLabel} 配置的是文字模型 ${token}。语音测试需要 Gemini Live / Native Audio 模型；请修改 Prompt 模型，或在“Gemini Live 模型”输入框里手动覆盖。`;
}

export function describeVoiceTabOverrideWarning(
  model: string | null | undefined,
  translate?: ModelWarningTranslator
): string | null {
  const token = (model ?? '').trim();
  if (!token || isLiveModelId(token)) {
    return null;
  }

  if (translate) {
    return translate('pages:test.modelWarnings.voiceOverrideUsesTextModel', {
      defaultValue:
        'The current voice session model {{modelId}} is not a Gemini Live / Native Audio model. Switch to a voice model before connecting, or select a prompt that already uses one.',
      modelId: token,
    });
  }
  return `当前语音会话模型 ${token} 不是 Gemini Live / Native Audio 模型。连接前请改成语音模型，或重新选择一个使用语音模型的 Prompt。`;
}
