import { describe, expect, it } from 'vitest';

import { matchGeminiLiveVoice, resolveGeminiLiveVoice } from './voiceSelection';

const SUPPORTED_VOICES = ['Aoede', 'Orus', 'Zephyr'];

describe('voiceSelection', () => {
  it('maps Twilio Google Chirp voice ids to Gemini short names', () => {
    expect(
      matchGeminiLiveVoice('ja-JP-Chirp3-HD-Aoede', {
        supportedVoices: SUPPORTED_VOICES,
      })
    ).toBe('Aoede');
  });

  it('rejects non-Gemini vendor voices and falls back to the default voice', () => {
    expect(
      matchGeminiLiveVoice('3JDquces8E8bkmvbh6Bc', {
        supportedVoices: SUPPORTED_VOICES,
      })
    ).toBeNull();
    expect(
      resolveGeminiLiveVoice('Mizuki', {
        supportedVoices: SUPPORTED_VOICES,
        defaultVoice: 'Aoede',
      })
    ).toBe('Aoede');
  });

  it('rejects prompt voices from non-Gemini providers', () => {
    expect(
      matchGeminiLiveVoice('Aoede', {
        voiceProvider: 'amazon',
        supportedVoices: SUPPORTED_VOICES,
      })
    ).toBeNull();
  });
});
