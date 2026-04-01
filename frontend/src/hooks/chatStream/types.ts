export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  template_code: string;
  provider?: string;
  model?: string;
  temperature?: number;
  call_id?: string;
}

export interface SSEEvent {
  type: 'call_id' | 'content' | 'done' | 'error';
  call_id?: string;
  content?: string;
  error?: string;
  tokens_used?: number;
}

export interface UseChatStreamReturn {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  callId: string | null;
  totalTokens: number;
  sendMessage: (content: string, options?: Partial<ChatRequest>) => Promise<void>;
  retryLastMessage: () => Promise<void>;
  dismissError: () => void;
  clearMessages: () => void;
}
