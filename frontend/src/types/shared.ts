export type CallDirection = 'inbound' | 'outbound';
export type CallStatus = 'ongoing' | 'completed' | 'failed';

export interface CallLog {
  id: string;
  direction: CallDirection;
  counterpart: string;
  startedAt: string;
  durationSeconds: number;
  status: CallStatus;
  summary?: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  modelId: string;
  systemPrompt: string;
  instructions: string;
  welcomeMessage?: string;
  closingMessage?: string;
  capabilities: PromptCapabilities;
  voiceConfig?: VoiceConfig;
  updatedAt: string;
  version: string;
}

export interface PromptFormValues {
  name: string;
  modelId: string;
  systemPrompt: string;
  welcomeMessage?: string;
  closingMessage?: string;
  capabilities: PromptCapabilities;
  version: string;
  voiceConfig?: VoiceConfig;
}

export interface PromptCapabilities {
  appointmentLogging: boolean;
  ttsEnabled: boolean;
}

export interface AgentProfile {
  id: string;
  name: string;
  llmProvider: 'openai' | 'anthropic' | 'azure';
  voice: string;
  temperature: number;
}

export interface VoiceConfig {
  voice?: string;
  speakingRate?: number;
  noiseSuppression?: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  description?: string;
}

export interface ReservationRecord {
  id: string;
  timestamp: string;
  callerName: string;
  company: string;
  appointment: string;
  category: string;
  amount: string;
  address: string;
  summary: string;
  extraRequest: string;
  rawMessages: string;
  operation: 'create' | 'update' | 'delete';
}

export interface Appointment {
  id: string;
  call_id?: string;
  timestamp: string;
  caller_name: string;
  company?: string;
  appointment: string;
  category?: string;
  amount?: string;
  address?: string;
  summary?: string;
  extra_request?: string;
  raw_messages?: any;
  operation?: string;
}

export interface AppointmentsResponse {
  items: Appointment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
