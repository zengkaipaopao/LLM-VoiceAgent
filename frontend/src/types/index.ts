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
  systemPrompt: string;
  updatedAt: string;
  version: string;
}

export interface AgentProfile {
  id: string;
  name: string;
  llmProvider: 'openai' | 'anthropic' | 'azure';
  voice: string;
  temperature: number;
}
