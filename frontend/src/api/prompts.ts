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
    // If it's a FormValues, construct API payload
    // We need to handle Partial<PromptTemplate> vs PromptFormValues
    
    // Common fields
    const apiPayload: any = {
        name: payload.name,
        code: (payload as any).code, // code might be in both
        description: (payload as any).description,
        category: (payload as any).category,
        
        llm_provider: (payload as any).llmProvider,
        llm_model: (payload as any).llmModel,
        temperature: (payload as any).temperature,
        max_tokens: (payload as any).maxTokens,
        
        system_prompt: (payload as any).systemPrompt,
        extraction_prompt: (payload as any).extractionPrompt,
        // extraction_schema  (payload as any).extractionSchema ?? undefined
        
        response_format: (payload as any).responseFormat,
        output_schema: typeof (payload as any).outputSchema === 'string' 
            ? tryParseJson((payload as any).outputSchema) 
            : (payload as any).outputSchema,
        
        voice_provider: (payload as any).voiceProvider,
        voice_id: (payload as any).voiceId,
        // voice_settings
        
        // Legacy mapping if needed? Backend handles new fields.
        // We might want to clear old fields if they exist?
    };
    
    // Cleanup undefined
    Object.keys(apiPayload).forEach(key => apiPayload[key] === undefined && delete apiPayload[key]);
    
    return apiPayload;
};

// Simplified Payload Creator for Create/Update
const toCreatePayload = (values: PromptFormValues) => ({
    name: values.name,
    code: values.code,
    description: values.description,
    category: values.category,
    
    llm_provider: values.llmProvider,
    llm_model: values.llmModel,
    temperature: values.temperature,
    max_tokens: values.maxTokens,
    
    system_prompt: values.systemPrompt,
    extraction_prompt: values.extractionPrompt,
    
    response_format: values.responseFormat,
    output_schema: values.outputSchema ? tryParseJson(values.outputSchema) : undefined,
    
    voice_provider: values.voiceProvider,
    voice_id: values.voiceId,
});

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
    // For partial update, we just map fields. 
    // Simplified mapping for now, assuming only new fields matter mostly.
    const apiPayload: any = {};
    if (payload.name) apiPayload.name = payload.name;
    if (payload.llmProvider) apiPayload.llm_provider = payload.llmProvider;
    if (payload.llmModel) apiPayload.llm_model = payload.llmModel;
    if (payload.temperature !== undefined) apiPayload.temperature = payload.temperature;
    if (payload.maxTokens !== undefined) apiPayload.max_tokens = payload.maxTokens;
    if (payload.systemPrompt) apiPayload.system_prompt = payload.systemPrompt;
    if (payload.responseFormat) apiPayload.response_format = payload.responseFormat;
    if (payload.outputSchema) {
        apiPayload.output_schema = typeof payload.outputSchema === 'string'
            ? tryParseJson(payload.outputSchema)
            : payload.outputSchema;
    }
    
    // Add more if needed
    
  const response = await http.put(`/prompts/${id}`, apiPayload);
  return mapPrompt(response.data.data);
}

export async function createPrompt(payload: PromptFormValues) {
  const response = await http.post('/prompts', toCreatePayload(payload));
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
