import { GoogleLanguageOption, GoogleVoiceOption, TtsModelOption, TtsProviderOption } from './ttsTypes';

export const ttsProviderOptions: readonly TtsProviderOption[] = [
  { id: 'openai', label: 'OpenAI gpt-4o-mini-tts' },
  { id: 'google', label: 'Google Cloud Text-to-Speech' },
];

export const ttsModelOptions: Record<TtsProviderOption['id'], TtsModelOption[]> = {
  openai: [{ id: 'gpt-4o-mini-tts', label: 'gpt-4o-mini-tts' }],
  google: [
    { id: 'google-wavenet', label: 'Wavenet（标准）' },
    { id: 'google-neural2', label: 'Neural2（自然）' },
    { id: 'google-studio', label: 'Studio（高保真）' },
  ],
};

export const openAiVoiceOptions: GoogleVoiceOption[] = [
  { id: 'alloy', label: 'alloy' },
  { id: 'ballad', label: 'ballad' },
  { id: 'verse', label: 'verse' },
  { id: 'sage', label: 'sage' },
  { id: 'marin', label: 'marin' },
  { id: 'coral', label: 'coral' },
  { id: 'echo', label: 'echo' },
  { id: 'ash', label: 'ash' },
  { id: 'shimmer', label: 'shimmer' },
];

export const googleLanguageOptions: GoogleLanguageOption[] = [
  {
    code: 'ja-JP',
    label: '日语',
    voices: [
      { id: 'ja-JP-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'ja-JP-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'ja-JP-Wavenet-C', label: 'Wavenet C · 女声' },
      { id: 'ja-JP-Wavenet-D', label: 'Wavenet D · 男声' },
      { id: 'ja-JP-Neural2-C', label: 'Neural2 C · 女声' },
      { id: 'ja-JP-Neural2-D', label: 'Neural2 D · 男声' },
      { id: 'ja-JP-Studio-Q', label: 'Studio Q · 女声' },
    ],
  },
  {
    code: 'en-US',
    label: '英语（美国）',
    voices: [
      { id: 'en-US-Wavenet-D', label: 'Wavenet D · 男声' },
      { id: 'en-US-Wavenet-F', label: 'Wavenet F · 女声' },
      { id: 'en-US-Neural2-H', label: 'Neural2 H · 女声' },
      { id: 'en-US-Neural2-I', label: 'Neural2 I · 男声' },
      { id: 'en-US-Studio-O', label: 'Studio O · 女声' },
    ],
  },
  {
    code: 'zh-CN',
    label: '中文（普通话）',
    voices: [
      { id: 'cmn-CN-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'cmn-CN-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'cmn-CN-Wavenet-C', label: 'Wavenet C · 女声' },
      { id: 'cmn-CN-Neural2-D', label: 'Neural2 D · 女声' },
    ],
  },
  {
    code: 'ko-KR',
    label: '韩语',
    voices: [
      { id: 'ko-KR-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'ko-KR-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'ko-KR-Neural2-C', label: 'Neural2 C · 女声' },
    ],
  },
];

export const getGoogleVoices = (languageCode: string): GoogleVoiceOption[] => {
  return googleLanguageOptions.find((language) => language.code === languageCode)?.voices ?? [];
};
