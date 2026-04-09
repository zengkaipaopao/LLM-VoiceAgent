import { useCallback, useEffect, useState } from 'react';

import {
  FALLBACK_GEMINI_VOICES,
  fetchGeminiVoiceCatalog,
  type GeminiVoiceCatalog,
} from '../api/geminiVoices';

interface UseGeminiVoiceCatalogOptions {
  enabled?: boolean;
}

interface UseGeminiVoiceCatalogResult {
  voiceCatalog: GeminiVoiceCatalog;
  loadingVoices: boolean;
  voiceLoadError: string | null;
  refreshVoiceCatalog: (options?: { forceRefresh?: boolean }) => Promise<void>;
}

const FALLBACK_VOICE_CATALOG: GeminiVoiceCatalog = {
  voices: [...FALLBACK_GEMINI_VOICES],
  source: 'fallback_static',
  defaultVoice: 'Aoede',
};

export function useGeminiVoiceCatalog(
  options: UseGeminiVoiceCatalogOptions = {}
): UseGeminiVoiceCatalogResult {
  const enabled = options.enabled ?? true;
  const [voiceCatalog, setVoiceCatalog] = useState<GeminiVoiceCatalog>(FALLBACK_VOICE_CATALOG);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [voiceLoadError, setVoiceLoadError] = useState<string | null>(null);

  const refreshVoiceCatalog = useCallback(async (refreshOptions?: { forceRefresh?: boolean }) => {
    setLoadingVoices(true);
    try {
      const catalog = await fetchGeminiVoiceCatalog(refreshOptions);
      setVoiceCatalog({
        voices: catalog.voices.length ? catalog.voices : [...FALLBACK_GEMINI_VOICES],
        source: catalog.source,
        defaultVoice: catalog.defaultVoice || 'Aoede',
      });
      setVoiceLoadError(null);
    } catch (error) {
      setVoiceCatalog(FALLBACK_VOICE_CATALOG);
      setVoiceLoadError(error instanceof Error ? error.message : String(error));
    } finally {
      setLoadingVoices(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void refreshVoiceCatalog();
  }, [enabled, refreshVoiceCatalog]);

  return {
    voiceCatalog,
    loadingVoices,
    voiceLoadError,
    refreshVoiceCatalog,
  };
}
