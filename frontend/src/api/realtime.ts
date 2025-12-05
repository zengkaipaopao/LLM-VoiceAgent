import { http } from './http';

export type RealtimeSessionResponse = {
  session_id: string;
  model: string;
  expires_at?: number;
  client_secret: string;
  websocket_url?: string | null;
  rtc_configuration?: Record<string, unknown> | null;
};

export type RealtimeSessionParams = {
  model?: string;
  voice?: string;
  instructions?: string;
  sip?: Record<string, unknown>;
};

export async function createRealtimeSession(params?: RealtimeSessionParams) {
  const response = await http.post<RealtimeSessionResponse>('/realtime/session', params ?? {});
  return response.data;
}
