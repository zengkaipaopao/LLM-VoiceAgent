export type CallDirection = 'inbound' | 'outbound';
export type CallStatus = 'ongoing' | 'completed' | 'failed';

export interface CallLog {
  id: string;
  direction: CallDirection;
  counterpart: string;
  callerName?: string;
  startedAt: string;
  answeredAt?: string;
  endedAt?: string;
  durationSeconds: number;
  status: CallStatus;
  handlerType?: string;
  isAnswered: boolean;
  aiConfidence?: number;
  summary?: string;
  transcript?: string;
  createdAt: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  code: string;
  description?: string;
  category?: string;
  modelId?: string; // Legacy
  
  // LLM Config
  llmProvider: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  
  // Content
  systemPrompt: string;
  extractionPrompt?: string;
  extractionSchema?: Record<string, any>;
  
  // Output Config
  responseFormat?: 'text' | 'json_object';
  outputSchema?: Record<string, any>; // JSON schema
  
  // Voice Config
  voiceProvider?: string;
  voiceId?: string;
  voiceSettings?: Record<string, any>;
  
  // Legacy fields mapped
  instructions?: string;
  welcomeMessage?: string;
  closingMessage?: string;
  capabilities?: PromptCapabilities;
  voiceConfig?: VoiceConfig; // Legacy
  
  updatedAt: string;
  version: number;
  isActive: boolean;
}

export interface PromptFormValues {
  name: string;
  code: string;
  description?: string;
  category?: string;
  
  llmProvider: string;
  llmModel: string;
  temperature: number;
  maxTokens: number;
  
  systemPrompt: string;
  extractionPrompt?: string;
  
  responseFormat?: 'text' | 'json_object';
  outputSchema?: string; // String for editor
  
  voiceProvider?: string;
  voiceId?: string;
  
  // Legacy
  capabilities?: PromptCapabilities;
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
  is_handled?: boolean;
}

export interface AppointmentsResponse {
  items: Appointment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
