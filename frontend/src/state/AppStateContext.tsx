import { ReactNode, createContext, useContext, useMemo } from 'react';
import {
  AgentProfile,
  CallLog,
  CreateModelPayload,
  ModelInfo,
  PromptFormValues,
  PromptTemplate,
  ReservationRecord,
} from '../types';
import { usePromptsStore } from './stores/usePromptsStore';
import { useModelsStore } from './stores/useModelsStore';
import { useReservationsStore } from './stores/useReservationsStore';
import { useCallsStore } from './stores/useCallsStore';
import { useAgentsStore } from './stores/useAgentsStore';

type AppState = {
  calls: CallLog[];
  reservations: ReservationRecord[];
  reloadReservations: () => Promise<void>;
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
  const { reservations, loadingReservations, reloadReservations } = useReservationsStore();
  const { calls } = useCallsStore();
  const { agents } = useAgentsStore();

  const value = useMemo(
    () => ({
      calls,
      prompts,
      reservations,
      reloadReservations,
      models,
      allowedModels,
      agents,
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
      reloadReservations,
      calls,
      agents,
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
