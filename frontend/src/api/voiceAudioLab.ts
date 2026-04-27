import { z } from 'zod';

import { http } from './http';

const VoiceAudioLabVariantSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string(),
  sample_rate: z.number(),
  pcm_mime_type: z.string(),
  duration_ms: z.number(),
  bytes: z.number(),
  rms: z.number(),
  peak: z.number(),
  pcm_base64: z.string(),
  wav_base64: z.string(),
});

const VoiceAudioLabPrepareSchema = z.object({
  sample_rate: z.number(),
  variants: z.array(VoiceAudioLabVariantSchema),
});

const VoiceAudioLabEvaluateSchema = z.object({
  variant_id: z.string().nullable().optional(),
  prompt_code: z.string(),
  model: z.string(),
  session_id: z.string().nullable().optional(),
  opening_already_played: z.boolean(),
  opening_text: z.string().nullable().optional(),
  original_sample_rate: z.number(),
  effective_send_sample_rate: z.number(),
  input_partials: z.array(z.string()),
  input_final: z.string(),
  output_partials: z.array(z.string()),
  output_final: z.string(),
  assistant_meta_texts: z.array(z.string()),
  turn_complete: z.boolean(),
  timed_out: z.boolean(),
  usage: z
    .object({
      total_tokens: z.number(),
      prompt_tokens: z.number(),
      response_tokens: z.number(),
    })
    .nullable()
    .optional(),
  event_types: z.array(z.string()),
});

export interface VoiceAudioLabVariant {
  id: string;
  label: string;
  description: string;
  sampleRate: number;
  pcmMimeType: string;
  durationMs: number;
  bytes: number;
  rms: number;
  peak: number;
  pcmBase64: string;
  wavBase64: string;
}

export interface PrepareVoiceAudioLabRequest {
  audioBase64: string;
  sampleRate: number;
}

export interface EvaluateVoiceAudioLabRequest {
  audioBase64: string;
  sampleRate: number;
  promptCode?: string;
  voiceName?: string;
  openingAlreadyPlayed: boolean;
  variantId?: string;
}

export interface VoiceAudioLabEvaluation {
  variantId: string | null;
  promptCode: string;
  model: string;
  sessionId: string | null;
  openingAlreadyPlayed: boolean;
  openingText: string | null;
  originalSampleRate: number;
  effectiveSendSampleRate: number;
  inputPartials: string[];
  inputFinal: string;
  outputPartials: string[];
  outputFinal: string;
  assistantMetaTexts: string[];
  turnComplete: boolean;
  timedOut: boolean;
  usage: {
    totalTokens: number;
    promptTokens: number;
    responseTokens: number;
  } | null;
  eventTypes: string[];
}

function toVariant(payload: z.infer<typeof VoiceAudioLabVariantSchema>): VoiceAudioLabVariant {
  return {
    id: payload.id,
    label: payload.label,
    description: payload.description,
    sampleRate: payload.sample_rate,
    pcmMimeType: payload.pcm_mime_type,
    durationMs: payload.duration_ms,
    bytes: payload.bytes,
    rms: payload.rms,
    peak: payload.peak,
    pcmBase64: payload.pcm_base64,
    wavBase64: payload.wav_base64,
  };
}

export async function prepareVoiceAudioLab(
  payload: PrepareVoiceAudioLabRequest
): Promise<{ sampleRate: number; variants: VoiceAudioLabVariant[] }> {
  const response = await http.post('/twilio/voice/trace/audio-lab/prepare', {
    audio_base64: payload.audioBase64,
    sample_rate: payload.sampleRate,
  });
  const parsed = VoiceAudioLabPrepareSchema.parse(response.data.data);
  return {
    sampleRate: parsed.sample_rate,
    variants: parsed.variants.map(toVariant),
  };
}

export async function evaluateVoiceAudioLab(
  payload: EvaluateVoiceAudioLabRequest
): Promise<VoiceAudioLabEvaluation> {
  const response = await http.post(
    '/twilio/voice/trace/audio-lab/evaluate',
    {
      audio_base64: payload.audioBase64,
      sample_rate: payload.sampleRate,
      prompt_code: payload.promptCode,
      voice_name: payload.voiceName,
      opening_already_played: payload.openingAlreadyPlayed,
      variant_id: payload.variantId,
    },
    {
      timeout: 60_000,
    }
  );
  const parsed = VoiceAudioLabEvaluateSchema.parse(response.data.data);
  return {
    variantId: parsed.variant_id ?? null,
    promptCode: parsed.prompt_code,
    model: parsed.model,
    sessionId: parsed.session_id ?? null,
    openingAlreadyPlayed: parsed.opening_already_played,
    openingText: parsed.opening_text ?? null,
    originalSampleRate: parsed.original_sample_rate,
    effectiveSendSampleRate: parsed.effective_send_sample_rate,
    inputPartials: parsed.input_partials,
    inputFinal: parsed.input_final,
    outputPartials: parsed.output_partials,
    outputFinal: parsed.output_final,
    assistantMetaTexts: parsed.assistant_meta_texts,
    turnComplete: parsed.turn_complete,
    timedOut: parsed.timed_out,
    usage: parsed.usage
      ? {
          totalTokens: parsed.usage.total_tokens,
          promptTokens: parsed.usage.prompt_tokens,
          responseTokens: parsed.usage.response_tokens,
        }
      : null,
    eventTypes: parsed.event_types,
  };
}
