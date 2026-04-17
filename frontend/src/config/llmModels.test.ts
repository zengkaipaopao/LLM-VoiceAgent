import { describe, expect, it } from 'vitest';

import {
  describeTextTabModelWarning,
  describeVoiceTabOverrideWarning,
  describeVoiceTabPromptModelWarning,
} from './llmModels';

describe('llm model compatibility hints', () => {
  const translate = (key: string, options: { defaultValue: string; [key: string]: unknown }) =>
    `${key}:${String(options.modelId ?? options.promptCode ?? options.defaultValue)}`;

  it('warns when a live model is selected for text testing', () => {
    expect(
      describeTextTabModelWarning('gemini-2.5-flash-native-audio-latest', 'base_appointment')
    ).toContain('文字测试无法使用该模型');
  });

  it('warns when a generate model is selected for voice testing via prompt', () => {
    expect(
      describeVoiceTabPromptModelWarning('gemini-2.5-flash', 'base_appointment')
    ).toContain('语音测试需要 Gemini Live / Native Audio 模型');
  });

  it('warns when a manual voice override is not a live model', () => {
    expect(describeVoiceTabOverrideWarning('gemini-2.5-flash')).toContain('不是 Gemini Live / Native Audio 模型');
  });

  it('uses the provided translator when building model warnings', () => {
    expect(
      describeTextTabModelWarning('gemini-2.5-flash-native-audio-latest', 'base_appointment', translate)
    ).toBe('pages:test.modelWarnings.textPromptUsesVoiceModel:gemini-2.5-flash-native-audio-latest');
    expect(
      describeVoiceTabPromptModelWarning('gemini-2.5-flash', 'base_appointment', translate)
    ).toBe('pages:test.modelWarnings.voicePromptUsesTextModel:gemini-2.5-flash');
    expect(describeVoiceTabOverrideWarning('gemini-2.5-flash', translate)).toBe(
      'pages:test.modelWarnings.voiceOverrideUsesTextModel:gemini-2.5-flash'
    );
  });

  it('returns null when the current model matches the target transport', () => {
    expect(describeTextTabModelWarning('gemini-2.5-flash', 'base_appointment')).toBeNull();
    expect(describeVoiceTabPromptModelWarning('gemini-2.5-flash-native-audio-latest', 'base_appointment')).toBeNull();
    expect(describeVoiceTabOverrideWarning('gemini-2.5-flash-native-audio-latest')).toBeNull();
  });
});
