import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { AgentProfile, CallLog, ModelInfo, PromptTemplate } from '../types';
import { fetchPrompts, updatePrompt as updatePromptApi } from '../api/prompts';
import { fetchAllowedModels, fetchModels, updateAllowedModels as updateAllowedModelsApi } from '../api/models';

type AppState = {
  calls: CallLog[];
  prompts: PromptTemplate[];
  models: ModelInfo[];
  allowedModels: string[];
  agents: AgentProfile[];
  updatePromptTemplate: (id: string, patch: Partial<PromptTemplate>) => Promise<PromptTemplate>;
  updateAllowedModels: (ids: string[]) => Promise<string[]>;
  loadingPrompts: boolean;
  loadingModels: boolean;
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
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);

  const loadPrompts = useCallback(async () => {
    setLoadingPrompts(true);
    try {
      const data = await fetchPrompts();
      setPrompts(data);
    } catch (error) {
      console.error('加载 Prompt 配置失败', error);
      setPrompts([]);
    } finally {
      setLoadingPrompts(false);
    }
  }, []);

  const loadModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const data = await fetchModels();
      setModels(data);
      const allowed = await fetchAllowedModels();
      setAllowedModels(allowed);
    } catch (error) {
      console.error('加载模型列表失败', error);
      setModels([]);
      setAllowedModels([]);
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    void loadPrompts();
    void loadModels();
  }, [loadPrompts, loadModels]);

  const updatePromptTemplate = useCallback(async (id: string, patch: Partial<PromptTemplate>) => {
    const updated = await updatePromptApi(id, patch);
    setPrompts((prev) => prev.map((prompt) => (prompt.id === id ? updated : prompt)));
    return updated;
  }, []);

  const updateAllowedModels = useCallback(async (ids: string[]) => {
    const updated = await updateAllowedModelsApi(ids);
    setAllowedModels(updated);
    return updated;
  }, []);

  const value = useMemo(
    () => ({
      calls: mockCalls,
      prompts,
      models,
      allowedModels,
      agents: mockAgents,
      updatePromptTemplate,
      updateAllowedModels,
      loadingPrompts,
      loadingModels,
    }),
    [allowedModels, models, prompts, updateAllowedModels, updatePromptTemplate, loadingModels, loadingPrompts],
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
