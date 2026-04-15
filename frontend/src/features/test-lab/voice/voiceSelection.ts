const ELEVENLABS_VOICE_ID_PATTERN =
  /^[A-Za-z0-9]{20}(?:-[A-Za-z0-9_.]+)?(?:-[0-9.]+(?:_[0-9.]+){2})?$/;

function resolveCaseInsensitiveVoice(value: string | null | undefined, supportedVoices: string[]): string | null {
  const token = (value || '').trim().toLowerCase();
  if (!token) return null;
  return supportedVoices.find((voice) => voice.trim().toLowerCase() === token) ?? null;
}

export function matchGeminiLiveVoice(
  value: string | null | undefined,
  options: {
    voiceProvider?: string | null;
    supportedVoices: string[];
  }
): string | null {
  const providerToken = (options.voiceProvider || '').trim().toLowerCase();
  if (providerToken && providerToken !== 'google' && providerToken !== 'gemini') {
    return null;
  }

  let token = (value || '').trim();
  if (!token) return null;
  if (token.startsWith('Google.')) {
    token = token.slice('Google.'.length).trim();
  }
  if (token.startsWith('Amazon.') || token.startsWith('ElevenLabs.')) {
    return null;
  }
  if (token.includes('-Chirp3-HD-')) {
    token = token.split('-Chirp3-HD-')[1]?.trim() || token;
  }
  if (ELEVENLABS_VOICE_ID_PATTERN.test(token)) {
    return null;
  }
  return resolveCaseInsensitiveVoice(token, options.supportedVoices);
}

export function resolveGeminiLiveVoice(
  value: string | null | undefined,
  options: {
    voiceProvider?: string | null;
    supportedVoices: string[];
    defaultVoice?: string | null;
  }
): string {
  return (
    matchGeminiLiveVoice(value, {
      voiceProvider: options.voiceProvider,
      supportedVoices: options.supportedVoices,
    }) ||
    resolveCaseInsensitiveVoice(options.defaultVoice || 'Aoede', options.supportedVoices) ||
    'Aoede'
  );
}
