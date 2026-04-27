export type VoiceRouteMode = 'direct' | 'twilio_official' | 'twilio_media_stream';

export interface DialogueHistoryItem {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timeLabel: string;
  ts: number;
}
