import { http } from './http';

type TtsResponsePayload = {
  audio_base64: string;
  content_type: string;
};

export type SynthesizeSpeechPayload = {
  text: string;
  model: string;
  voice: string;
  provider?: 'openai' | 'google';
  languageCode?: string;
  speakingRate?: number;
  pitch?: number;
  format?: string;
};

export async function synthesizeSpeech(payload: SynthesizeSpeechPayload) {
  const response = await http.post<TtsResponsePayload>('/tts', payload);
  return {
    audioBase64: response.data.audio_base64,
    contentType: response.data.content_type,
  };
}
