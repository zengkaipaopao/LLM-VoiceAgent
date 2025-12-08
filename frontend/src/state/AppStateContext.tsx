import { ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  AgentProfile,
  CallLog,
  CreateModelPayload,
  ModelInfo,
  PromptFormValues,
  PromptTemplate,
  ReservationRecord,
} from '../types';
import { fetchAppointments } from '../api/appointments';
import { usePromptsStore } from './stores/usePromptsStore';
import { useModelsStore } from './stores/useModelsStore';

type AppState = {
  calls: CallLog[];
  reservations: ReservationRecord[];
  prompts: PromptTemplate[];
  models: ModelInfo[];
  allowedModels: string[];
  agents: AgentProfile[];
  updatePromptTemplate: (id: string, patch: Partial<PromptTemplate>) => Promise<PromptTemplate>;
  createPromptTemplate: (payload: PromptFormValues) => Promise<PromptTemplate>;
  deletePromptTemplate: (id: string) => Promise<void>;
  updateAllowedModels: (ids: string[]) => Promise<string[]>;
  createCustomModel: (payload: CreateModelPayload) => Promise<ModelInfo>;
  deleteCustomModel: (modelId: string) => Promise<void>;
  loadingPrompts: boolean;
  loadingModels: boolean;
  loadingReservations: boolean;
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
  const {
    prompts,
    loadingPrompts,
    updatePromptTemplate,
    createPromptTemplate,
    deletePromptTemplate,
  } = usePromptsStore();
  const {
    models,
    allowedModels,
    loadingModels,
    updateAllowedModels,
    createCustomModel,
    deleteCustomModel,
  } = useModelsStore();
  const [reservations, setReservations] = useState<ReservationRecord[]>([]);
  const [loadingReservations, setLoadingReservations] = useState(false);

  const loadReservations = useCallback(async () => {
    setLoadingReservations(true);
    try {
      const data = await fetchAppointments();
      setReservations(data);
    } catch (error) {
      console.error('加载预约记录失败', error);
      setReservations([]);
    } finally {
      setLoadingReservations(false);
    }
  }, []);

  useEffect(() => {
    void loadReservations();
  }, [loadReservations]);

  const value = useMemo(
    () => ({
      calls: mockCalls,
      prompts,
      reservations,
      models,
      allowedModels,
      agents: mockAgents,
      updatePromptTemplate,
      createPromptTemplate,
      deletePromptTemplate,
      updateAllowedModels,
      createCustomModel,
      deleteCustomModel,
      loadingPrompts,
      loadingModels,
      loadingReservations,
    }),
    [
      allowedModels,
      loadingModels,
      loadingPrompts,
      loadingReservations,
      models,
      prompts,
      reservations,
      createPromptTemplate,
      deletePromptTemplate,
      updateAllowedModels,
      createCustomModel,
      deleteCustomModel,
      updatePromptTemplate,
    ],
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
