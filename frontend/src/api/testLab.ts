import { http } from './http';

export interface StartTestSessionRequest {
  template_code: string;
  provider?: string;
  model?: string;
  caller_name?: string;
  mode?: 'text' | 'voice';
}

export interface StartTestSessionResponse {
  call_id: string;
  simulated_phone: string;
  started_at: string;
  template_code: string;
  llm_provider: string;
  llm_model: string;
}

export interface FinalizeTestSessionRequest {
  call_id: string;
  template_code?: string;
  run_extraction?: boolean;
}

export interface ExtractionSummary {
  success: boolean;
  appointment_id?: string | null;
  extracted_data: Record<string, unknown>;
  confidence: number;
  message: string;
}

export interface FinalizeTestSessionResponse {
  call_id: string;
  status: string;
  ended_at: string;
  duration_seconds: number;
  appointment_id?: string | null;
  extraction?: ExtractionSummary | null;
  already_extracted: boolean;
}

export interface AppendTestSessionMessagesRequest {
  call_id: string;
  template_code?: string;
  provider?: string;
  model?: string;
  messages: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
  }>;
}

export interface AppendTestSessionMessagesResponse {
  call_id: string;
  appended_count: number;
  transcript_length: number;
}

export async function startTestSession(
  payload: StartTestSessionRequest
): Promise<StartTestSessionResponse> {
  const response = await http.post('/chat/test/start', payload);
  return response.data.data;
}

export async function finalizeTestSession(
  payload: FinalizeTestSessionRequest
): Promise<FinalizeTestSessionResponse> {
  const response = await http.post('/chat/test/finalize', payload);
  return response.data.data;
}

export async function appendTestSessionMessages(
  payload: AppendTestSessionMessagesRequest
): Promise<AppendTestSessionMessagesResponse> {
  const response = await http.post('/chat/test/append-messages', payload);
  return response.data.data;
}
