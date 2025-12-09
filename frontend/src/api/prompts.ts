import { http } from './http';
import { PromptFormValues, PromptTemplate, VoiceConfig } from '../types';

type ApiPrompt = {
  id: string;
  name: string;
  model_id: string;
  system_prompt: string;
  instructions?: string;
  welcome_message?: string;
  closing_message?: string;
  enable_appointment_logging?: boolean;
  capabilities?: {
    appointment_logging?: boolean;
    tts_enabled?: boolean;
  };
  voice_config?: {
    voice?: string;
    speaking_rate?: number;
    noise_suppression?: boolean;
  };
  version: string;
  updated_at: string;
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

const mapPrompt = (prompt: ApiPrompt): PromptTemplate => ({
  id: prompt.id,
  name: prompt.name,
  modelId: prompt.model_id,
  systemPrompt: prompt.system_prompt,
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
});

const toApiPayload = (payload: Partial<PromptTemplate> | PromptFormValues) => ({
  name: payload.name,
  model_id: payload.modelId,
  system_prompt: payload.systemPrompt,
  welcome_message: payload.welcomeMessage,
  closing_message: payload.closingMessage,
  capabilities: payload.capabilities
    ? {
        appointment_logging: payload.capabilities.appointmentLogging,
        tts_enabled: payload.capabilities.ttsEnabled,
      }
    : undefined,
  enable_appointment_logging: undefined,
  voice_config: toApiVoiceConfig(payload.voiceConfig),
  version: payload.version,
});

export async function fetchPrompts() {
  const response = await http.get<ApiPrompt[]>('/prompts');
  return response.data.map(mapPrompt);
}

export async function updatePrompt(id: string, payload: Partial<PromptTemplate>) {
  const response = await http.put<ApiPrompt>(`/prompts/${id}`, toApiPayload(payload));
  return mapPrompt(response.data);
}

export async function createPrompt(payload: PromptFormValues) {
  const response = await http.post<ApiPrompt>('/prompts', toApiPayload(payload));
  return mapPrompt(response.data);
}

export async function deletePrompt(id: string) {
  await http.delete(`/prompts/${id}`);
}
