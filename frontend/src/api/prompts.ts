import { z } from 'zod';

import { DEFAULT_GENERATE_MODEL } from '../config/llmModels';
import { http } from './http';
import { LlmModelCapability, LlmModelOption, PromptFormValues, PromptTemplate, VoiceConfig } from '../types/shared';

const JsonObjectSchema = z.record(z.string(), z.unknown());

const parseJsonObject = (value: unknown): Record<string, unknown> | undefined => {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return undefined;
    }
    return undefined;
  }

  if (typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return undefined;
};

const OptionalJsonObjectSchema = z.preprocess(
  (value) => parseJsonObject(value),
  JsonObjectSchema.optional()
);

const ApiVoiceConfigSchema = z
  .object({
    voice: z.string().optional(),
    speaking_rate: z.number().optional(),
    noise_suppression: z.boolean().optional(),
  })
  .optional();

const ApiPromptSchema = z.object({
  id: z.string(),
  name: z.string(),
  code: z.string(),
  description: z.string().optional().nullable(),
  category: z.string().optional().nullable(),
  llm_provider: z.string().optional().nullable(),
  llm_model: z.string().optional().nullable(),
  temperature: z.number().optional().nullable(),
  max_tokens: z.number().optional().nullable(),
  system_prompt: z.string(),
  extraction_prompt: z.string().optional().nullable(),
  extraction_schema: OptionalJsonObjectSchema,
  response_format: z.enum(['text', 'json_object']).optional().nullable(),
  output_schema: OptionalJsonObjectSchema,
  voice_provider: z.string().optional().nullable(),
  voice_id: z.string().optional().nullable(),
  voice_settings: OptionalJsonObjectSchema,
  instructions: z.string().optional().nullable(),
  welcome_message: z.string().optional().nullable(),
  closing_message: z.string().optional().nullable(),
  capabilities: z
    .object({
      appointment_logging: z.boolean().optional(),
      tts_enabled: z.boolean().optional(),
    })
    .optional()
    .nullable(),
  enable_appointment_logging: z.boolean().optional().nullable(),
  voice_config: ApiVoiceConfigSchema,
  version: z.number().nullable().optional(),
  updated_at: z.string(),
  is_active: z.boolean(),
});

const PromptListPayloadSchema = z.object({
  templates: z.array(ApiPromptSchema),
  total: z.number().optional(),
});

const ModelCapabilitySchema = z.enum(['generate', 'live', 'both', 'other']);

const PromptModelItemSchema = z.object({
  name: z.string(),
  capability: ModelCapabilitySchema.optional(),
  is_generate: z.boolean().optional(),
  is_live: z.boolean().optional(),
  supported_actions: z.array(z.string()).optional(),
});

const PromptModelsPayloadSchema = z.object({
  models: z.array(z.string()),
  items: z.array(PromptModelItemSchema).optional(),
  source: z.string().optional(),
  fetched_at: z.number().optional(),
});

type ApiPrompt = z.infer<typeof ApiPromptSchema>;
type PromptPayloadInput = {
  name?: string;
  code?: string;
  description?: string;
  category?: string;
  llmProvider?: string;
  llmModel?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  extractionPrompt?: string;
  extractionSchema?: unknown;
  responseFormat?: 'text' | 'json_object';
  outputSchema?: unknown;
  voiceProvider?: string;
  voiceId?: string;
};

const mapVoiceConfig = (config?: z.infer<typeof ApiVoiceConfigSchema>): VoiceConfig | undefined => {
  if (!config) {
    return undefined;
  }
  return {
    voice: config.voice ?? undefined,
    speakingRate: config.speaking_rate ?? undefined,
    noiseSuppression: config.noise_suppression ?? undefined,
  };
};

const mapPrompt = (prompt: ApiPrompt): PromptTemplate => ({
  id: prompt.id,
  name: prompt.name,
  code: prompt.code,
  description: prompt.description ?? undefined,
  category: prompt.category ?? undefined,
  llmProvider: prompt.llm_provider || 'gemini',
  llmModel: prompt.llm_model || DEFAULT_GENERATE_MODEL,
  temperature: prompt.temperature ?? 0.7,
  maxTokens: prompt.max_tokens ?? 2048,
  systemPrompt: prompt.system_prompt,
  extractionPrompt: prompt.extraction_prompt ?? undefined,
  extractionSchema: prompt.extraction_schema,
  responseFormat: prompt.response_format ?? undefined,
  outputSchema: prompt.output_schema,
  voiceProvider: prompt.voice_provider ?? undefined,
  voiceId: prompt.voice_id ?? undefined,
  voiceSettings: prompt.voice_settings,
  modelId: prompt.llm_model || DEFAULT_GENERATE_MODEL,
  instructions: prompt.instructions ?? prompt.system_prompt,
  welcomeMessage: prompt.welcome_message ?? undefined,
  closingMessage: prompt.closing_message ?? undefined,
  capabilities: {
    appointmentLogging:
      prompt.capabilities?.appointment_logging ?? prompt.enable_appointment_logging ?? false,
    ttsEnabled: prompt.capabilities?.tts_enabled ?? false,
  },
  voiceConfig: mapVoiceConfig(prompt.voice_config),
  version: prompt.version ?? 1,
  updatedAt: prompt.updated_at,
  isActive: prompt.is_active,
});

const toApiPayload = (payload: PromptPayloadInput): Record<string, unknown> => {
  const extractionSchema = parseJsonObject(payload.extractionSchema);
  const outputSchema = parseJsonObject(payload.outputSchema);
  const compatibleExtractionSchema = extractionSchema ?? outputSchema;

  const apiPayload: Record<string, unknown> = {
    name: payload.name,
    code: payload.code,
    description: payload.description,
    category: payload.category,
    llm_provider: payload.llmProvider,
    llm_model: payload.llmModel,
    temperature: payload.temperature,
    max_tokens: payload.maxTokens,
    system_prompt: payload.systemPrompt,
    extraction_prompt: payload.extractionPrompt,
    extraction_schema: compatibleExtractionSchema,
    response_format: payload.responseFormat,
    output_schema: outputSchema,
    voice_provider: payload.voiceProvider,
    voice_id: payload.voiceId,
  };

  Object.keys(apiPayload).forEach((key) => {
    if (apiPayload[key] === undefined) {
      delete apiPayload[key];
    }
  });

  return apiPayload;
};

export async function fetchPrompts(): Promise<PromptTemplate[]> {
  const response = await http.get('/prompts');
  const payload = PromptListPayloadSchema.parse(response.data.data);
  return payload.templates.map(mapPrompt);
}

export async function fetchPrompt(id: string): Promise<PromptTemplate> {
  const response = await http.get(`/prompts/${id}`);
  const payload = ApiPromptSchema.parse(response.data.data);
  return mapPrompt(payload);
}

export async function updatePrompt(
  id: string,
  payload: Partial<PromptTemplate> | PromptFormValues
): Promise<PromptTemplate> {
  const response = await http.put(`/prompts/${id}`, toApiPayload(payload));
  const parsed = ApiPromptSchema.parse(response.data.data);
  return mapPrompt(parsed);
}

export async function createPrompt(payload: PromptFormValues): Promise<PromptTemplate> {
  const response = await http.post('/prompts', toApiPayload(payload));
  const parsed = ApiPromptSchema.parse(response.data.data);
  return mapPrompt(parsed);
}

export async function deletePrompt(id: string): Promise<void> {
  await http.delete(`/prompts/${id}`);
}

function modelCapabilityLabel(capability: LlmModelCapability): string {
  switch (capability) {
    case 'both':
      return '文本+实时';
    case 'generate':
      return '文本';
    case 'live':
      return '实时';
    default:
      return '其他';
  }
}

function capabilityOrder(capability: LlmModelCapability): number {
  switch (capability) {
    case 'both':
      return 0;
    case 'generate':
      return 1;
    case 'live':
      return 2;
    default:
      return 3;
  }
}

export async function fetchModels(provider: string): Promise<LlmModelOption[]> {
  const response = await http.get('/llm/models', { params: { provider } });
  const payload = PromptModelsPayloadSchema.parse(response.data.data);

  const fromItems = (payload.items || []).map((item) => {
    const value = item.name.trim();
    const capability = (item.capability || 'other') as LlmModelCapability;
    const isGenerate = item.is_generate ?? (capability === 'generate' || capability === 'both');
    const isLive = item.is_live ?? (capability === 'live' || capability === 'both');
    return {
      value,
      label: `[${modelCapabilityLabel(capability)}] ${value}`,
      capability,
      isGenerate,
      isLive,
    } satisfies LlmModelOption;
  });

  const existing = new Set(fromItems.map((item) => item.value));
  const fallbackOnly = payload.models
    .map((name) => name.trim())
    .filter((name) => name.length > 0 && !existing.has(name))
    .map(
      (value) =>
        ({
          value,
          label: `[其他] ${value}`,
          capability: 'other' as const,
          isGenerate: false,
          isLive: false,
        }) satisfies LlmModelOption
    );

  return [...fromItems, ...fallbackOnly].sort((a, b) => {
    const orderDiff = capabilityOrder(a.capability) - capabilityOrder(b.capability);
    if (orderDiff !== 0) return orderDiff;
    return a.value.localeCompare(b.value);
  });
}
