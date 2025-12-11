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
  reservationsLoaded: boolean;
  prompts: PromptTemplate[];
  loadPrompts: () => Promise<void>;
  promptsLoaded: boolean;
  models: ModelInfo[];
  allowedModels: string[];
  loadModels: () => Promise<void>;
  modelsLoaded: boolean;
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
    loadPrompts,
    promptsLoaded,
    updatePromptTemplate,
    createPromptTemplate,
    deletePromptTemplate,
  } = usePromptsStore();
  const {
    models,
    allowedModels,
    loadingModels,
    loadModels,
    modelsLoaded,
    updateAllowedModels,
    createCustomModel,
    deleteCustomModel,
  } = useModelsStore();
  const { reservations, loadingReservations, reloadReservations, reservationsLoaded } = useReservationsStore();
  const { calls } = useCallsStore();
  const { agents } = useAgentsStore();

  const value = useMemo(
    () => ({
      calls,
      prompts,
      reservations,
      reloadReservations,
      reservationsLoaded,
      loadPrompts,
      promptsLoaded,
      models,
      allowedModels,
      loadModels,
      modelsLoaded,
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
      agents,
      allowedModels,
      calls,
      createCustomModel,
      deleteCustomModel,
      loadingModels,
      loadingPrompts,
      loadingReservations,
      models,
      modelsLoaded,
      prompts,
      promptsLoaded,
      reservations,
      reservationsLoaded,
      reloadReservations,
      loadModels,
      loadPrompts,
      createPromptTemplate,
      deletePromptTemplate,
      updateAllowedModels,
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
