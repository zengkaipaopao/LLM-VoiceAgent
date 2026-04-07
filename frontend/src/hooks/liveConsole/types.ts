export type SocketStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
export type MicStatus = 'off' | 'starting' | 'on';

export interface LiveEventPayload {
  type?: string;
  text?: string;
  final?: boolean;
  message?: string;
  error?: string;
  data?: string;
  mime_type?: string;
  total_tokens?: number;
  session_id?: string;
  reason?: string | null;
}
