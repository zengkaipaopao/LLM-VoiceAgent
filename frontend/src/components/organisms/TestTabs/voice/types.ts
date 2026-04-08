export type VoiceRouteMode = 'direct' | 'twilio';

export interface DialogueHistoryItem {
  id: string;
  role: '用户' | 'AI';
  text: string;
  timeLabel: string;
  ts: number;
}
