import type { FinalizeTestSessionResponse, StartTestSessionResponse } from '../../api/testLab';
import type { PromptTemplate } from '../../types/shared';
import type { Message } from '../useChatStream';

export interface UseUnifiedTestLabResult {
  prompts: PromptTemplate[];
  loadingPrompts: boolean;
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  callerName: string;
  setCallerName: (value: string) => void;
  session: StartTestSessionResponse | null;
  messages: Message[];
  totalTokens: number;
  finalizeResult: FinalizeTestSessionResponse | null;
  isStarting: boolean;
  isSending: boolean;
  isFinalizing: boolean;
  error: string | null;
  setError: (value: string | null) => void;
  info: string | null;
  setInfo: (value: string | null) => void;
  selectedPrompt: PromptTemplate | undefined;
  quickMessages: string[];
  sessionClosed: boolean;
  sessionStatus: string;
  handleStartSession: () => Promise<void>;
  handleSendMessage: (content: string) => Promise<void>;
  handleFinalize: () => Promise<void>;
  handleClear: () => void;
}
