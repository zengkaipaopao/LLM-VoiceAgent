import { http } from './http';
import { PromptFormValues, PromptTemplate, VoiceConfig } from '../types/shared';

type ApiPrompt = {
  id: string;
  name: string;
  code: string;
  description?: string;
  category?: string;
  
  // LLM Config
  llm_provider?: string;
  llm_model?: string;
  temperature?: number;
  max_tokens?: number;
  
  // Content
  system_prompt: string;
  extraction_prompt?: string;
  extraction_schema?: Record<string, any>;
  
  // Output Config
  response_format?: 'text' | 'json_object';
  output_schema?: Record<string, any>;
  
  // Voice Config
  voice_provider?: string;
  voice_id?: string;
  voice_settings?: Record<string, any>; // JSON
  
  // Legacy / Mapped
  instructions?: string;
  welcome_message?: string;
  closing_message?: string;
  
  capabilities?: {
    appointment_logging?: boolean;
    tts_enabled?: boolean;
  };
  
  // Legacy direct fields
  enable_appointment_logging?: boolean; // Some old APIs might have this
  voice_config?: {
    voice?: string;
    speaking_rate?: number;
    noise_suppression?: boolean;
  };
  
  version: number;
  updated_at: string;
  is_active: boolean;
};

const mapVoiceConfig = (config?: ApiPrompt['voice_config']): VoiceConfig | undefined => {
  if (!config) return undefined;
  return {
    voice: config.voice ?? undefined,
    speakingRate: config.speaking_rate ?? undefined,
    noiseSuppression: config.noise_suppression ?? undefined,
  };
};

const toApiVoiceConfig = (config?: VoiceConfig) => {
  if (!config) return undefined;
  return {
    voice: config.voice,
    speaking_rate: config.speakingRate,
    noise_suppression: config.noiseSuppression,
  };
};

const tryParseJson = (str: string | undefined | null) => {
    if (!str) return undefined;
    try {
        return JSON.parse(str);
    } catch (e) {
        return undefined;
    }
}

const mapPrompt = (prompt: ApiPrompt): PromptTemplate => ({
  id: prompt.id,
  name: prompt.name,
  code: prompt.code,
  description: prompt.description,
  category: prompt.category,
  
  // LLM Config
  llmProvider: prompt.llm_provider || 'gemini',
  llmModel: prompt.llm_model || 'gemini-2.0-flash',
  temperature: prompt.temperature || 0.7,
  maxTokens: prompt.max_tokens || 2048,
  
  // Content
  systemPrompt: prompt.system_prompt,
  extractionPrompt: prompt.extraction_prompt,
  extractionSchema: prompt.extraction_schema,
  
  responseFormat: prompt.response_format,
  outputSchema: prompt.output_schema,
  
  // Voice Config
  voiceProvider: prompt.voice_provider,
  voiceId: prompt.voice_id,
  voiceSettings: prompt.voice_settings,
  
  // Legacy
  modelId: prompt.llm_model || 'gemini-2.0-flash', // Legacy mapping
  instructions: prompt.instructions ?? prompt.system_prompt,
  welcomeMessage: prompt.welcome_message ?? undefined,
  closingMessage: prompt.closing_message ?? undefined,
  capabilities: {
    appointmentLogging:
      prompt.capabilities?.appointment_logging ?? prompt.enable_appointment_logging ?? false,
    ttsEnabled: prompt.capabilities?.tts_enabled ?? false,
  },
  voiceConfig: mapVoiceConfig(prompt.voice_config),
  version: prompt.version,
  updatedAt: prompt.updated_at,
  isActive: prompt.is_active,
});

const toApiPayload = (payload: Partial<PromptTemplate> | PromptFormValues) => {
    const rawOutputSchema = (payload as any).outputSchema;
    const parsedOutputSchema =
      typeof rawOutputSchema === 'string' ? tryParseJson(rawOutputSchema) : rawOutputSchema;

    const rawExtractionSchema = (payload as any).extractionSchema;
    const parsedExtractionSchema =
      typeof rawExtractionSchema === 'string' ? tryParseJson(rawExtractionSchema) : rawExtractionSchema;

    // Prefer dedicated extraction schema; fallback to output schema for backward compatibility.
    const extractionSchema = parsedExtractionSchema ?? parsedOutputSchema;

    const apiPayload: any = {
        name: payload.name,
        code: (payload as any).code,
        description: (payload as any).description,
        category: (payload as any).category,

        llm_provider: (payload as any).llmProvider,
        llm_model: (payload as any).llmModel,
        temperature: (payload as any).temperature,
        max_tokens: (payload as any).maxTokens,

        system_prompt: (payload as any).systemPrompt,
        extraction_prompt: (payload as any).extractionPrompt,
        extraction_schema: extractionSchema,

        response_format: (payload as any).responseFormat,
        output_schema: parsedOutputSchema,

        voice_provider: (payload as any).voiceProvider,
        voice_id: (payload as any).voiceId,
    };

    Object.keys(apiPayload).forEach((key) => apiPayload[key] === undefined && delete apiPayload[key]);
    return apiPayload;
};

export async function fetchPrompts() {
  const response = await http.get('/prompts');
  // Backend returns ResponseBase[PromptTemplateListResponse]
  // response.data.data = { templates: ApiPrompt[], total: number }
  const payload = response.data.data;
  return (payload.templates || []).map(mapPrompt);
}

export async function fetchPrompt(id: string) {
    const response = await http.get(`/prompts/${id}`);
    return mapPrompt(response.data.data);
}

export async function updatePrompt(id: string, payload: Partial<PromptTemplate> | PromptFormValues) {
  const apiPayload = toApiPayload(payload);
  const response = await http.put(`/prompts/${id}`, apiPayload);
  return mapPrompt(response.data.data);
}

export async function createPrompt(payload: PromptFormValues) {
  const response = await http.post('/prompts', toApiPayload(payload));
  return mapPrompt(response.data.data);
}

export async function deletePrompt(id: string) {
  await http.delete(`/prompts/${id}`);
}

export async function fetchModels(provider: string): Promise<string[]> {
  const response = await http.get('/llm/models', {
    params: { provider },
  });
  return response.data.data.models;
}
