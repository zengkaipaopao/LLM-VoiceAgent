import { RefObject } from 'react';

export type ChatRole = 'user' | 'assistant';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  streaming?: boolean;
};

export type ConnectionState = 'idle' | 'connecting' | 'connected' | 'error';

export type ConnectionSummary = {
  label: string;
  type: string;
};

export type RealtimeSessionMeta = {
  id: string;
  model: string;
  expires_at?: number;
} | null;

export type SessionStats = {
  totalTurns: number;
  userTurns: number;
  assistantTurns: number;
  lastUpdated?: string;
};

export type ChatHistoryProps = {
  messages: ChatMessage[];
  historyRef: RefObject<HTMLDivElement>;
  formatTime: (timestamp?: string | number) => string;
  isAssistantTyping: boolean;
};
