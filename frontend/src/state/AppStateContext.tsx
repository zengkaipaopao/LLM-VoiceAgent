import { ReactNode, createContext, useCallback, useContext, useMemo, useState } from 'react';
import { AgentProfile, CallLog, PromptTemplate } from '../types';

type AppState = {
  calls: CallLog[];
  prompts: PromptTemplate[];
  agents: AgentProfile[];
  updatePromptTemplate: (id: string, patch: Partial<PromptTemplate>) => void;
};

const AppStateContext = createContext<AppState | undefined>(undefined);

const mockCalls: CallLog[] = [
  {
    id: 'call_1',
    direction: 'outbound',
    counterpart: '+1 415 555 0101',
    startedAt: new Date().toISOString(),
    durationSeconds: 420,
    status: 'completed',
    summary: '确认了客户需求并提交报价。',
  },
  {
    id: 'call_2',
    direction: 'inbound',
    counterpart: '+86 138 0000 0000',
    startedAt: new Date().toISOString(),
    durationSeconds: 180,
    status: 'failed',
    summary: '客户挂断，等待回拨。',
  },
];

const mockPrompts: PromptTemplate[] = [
  {
    id: 'prompt_1',
    name: '售前顾问',
    modelId: 'gpt-4o-realtime-preview-2024-12-17',
    systemPrompt: '你是专业的售前助手，帮助客户完成产品选型。',
    updatedAt: new Date().toISOString(),
    version: 'v1.0.0',
  },
  {
    id: 'prompt_2',
    name: '客服回访',
    modelId: 'gpt-4o-mini-2024-12-17',
    systemPrompt: '你负责售后回访并记录满意度。',
    updatedAt: new Date().toISOString(),
    version: 'v0.9.1',
  },
];

const mockAgents: AgentProfile[] = [
  {
    id: 'agent_1',
    name: 'Global Sales Bot',
    llmProvider: 'openai',
    voice: 'alloy',
    temperature: 0.3,
  },
  {
    id: 'agent_2',
    name: 'China Care Bot',
    llmProvider: 'azure',
    voice: 'ling',
    temperature: 0.5,
  },
];

type AppStateProviderProps = {
  children: ReactNode;
};

export function AppStateProvider({ children }: AppStateProviderProps) {
  const [prompts, setPrompts] = useState<PromptTemplate[]>(() => mockPrompts);

  const updatePromptTemplate = useCallback((id: string, patch: Partial<PromptTemplate>) => {
    setPrompts((prev) =>
      prev.map((prompt) =>
        prompt.id === id
          ? {
              ...prompt,
              ...patch,
              updatedAt: new Date().toISOString(),
            }
          : prompt,
      ),
    );
  }, []);

  const value = useMemo(
    () => ({
      calls: mockCalls,
      prompts,
      agents: mockAgents,
      updatePromptTemplate,
    }),
    [prompts, updatePromptTemplate],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error('useAppState must be used within AppStateProvider');
  }
  return context;
}
