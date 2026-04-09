import { z } from 'zod';

import { http } from './http';

const GeminiVoiceCatalogSchema = z.object({
  provider: z.literal('gemini').optional(),
  source: z.string(),
  fetched_at: z.number().optional(),
  voices: z.array(z.string()),
  default_voice: z.string(),
});

export const FALLBACK_GEMINI_VOICES = [
  'Zephyr',
  'Puck',
  'Charon',
  'Kore',
  'Fenrir',
  'Leda',
  'Orus',
  'Aoede',
  'Callirrhoe',
  'Autonoe',
  'Enceladus',
  'Iapetus',
  'Umbriel',
  'Algieba',
  'Despina',
  'Erinome',
  'Algenib',
  'Rasalgethi',
  'Laomedeia',
  'Achernar',
  'Alnilam',
  'Schedar',
  'Gacrux',
  'Pulcherrima',
  'Achird',
  'Zubenelgenubi',
  'Vindemiatrix',
  'Sadachbia',
  'Sadaltager',
  'Sulafat',
] as const;

export type GeminiVoiceCatalog = {
  voices: string[];
  source: string;
  defaultVoice: string;
};

export async function fetchGeminiVoiceCatalog(
  options?: { forceRefresh?: boolean }
): Promise<GeminiVoiceCatalog> {
  const response = await http.get('/twilio/voice/voices', {
    params: { force_refresh: Boolean(options?.forceRefresh) },
  });
  const payload = GeminiVoiceCatalogSchema.parse(response.data.data);

  return {
    voices: payload.voices,
    source: payload.source,
    defaultVoice: payload.default_voice,
  };
}
