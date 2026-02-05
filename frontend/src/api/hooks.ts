import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchAgents } from './agents';
import { fetchCalls } from './calls';
import { fetchAppointments, submitAppointmentRecord, AppointmentRecordPayload } from './appointments';
import { fetchAllowedModels, fetchModels, updateAllowedModels } from './models';
import { createPrompt, deletePrompt, fetchPrompts, updatePrompt } from './prompts';
import { PromptFormValues, PromptTemplate, ReservationRecord } from '../types/shared';

export function useCallsQuery() {
  return useQuery({
    queryKey: ['calls'],
    queryFn: fetchCalls,
    staleTime: 30_000,
  });
}

export function usePromptsQuery() {
  return useQuery({
    queryKey: ['prompts'],
    queryFn: fetchPrompts,
    staleTime: 30_000,
  });
}

export function useModelsQuery() {
  return useQuery({
    queryKey: ['models'],
    queryFn: fetchModels,
    staleTime: 60_000,
  });
}

export function useAllowedModelsQuery() {
  return useQuery({
    queryKey: ['models', 'allowed'],
    queryFn: fetchAllowedModels,
    staleTime: 60_000,
  });
}

export function useAppointmentsQuery() {
  return useQuery({
    queryKey: ['appointments'],
    queryFn: fetchAppointments,
  });
}

export function useAgentsQuery() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
    staleTime: Infinity,
  });
}

export function useCreatePromptMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PromptFormValues) => createPrompt(payload),
    onSuccess: (created) => {
      queryClient.setQueryData<PromptTemplate[]>(['prompts'], (prev) =>
        prev ? [...prev, created] : [created],
      );
    },
  });
}

export function useUpdatePromptMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<PromptTemplate> }) =>
      updatePrompt(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData<PromptTemplate[]>(['prompts'], (prev) =>
        prev ? prev.map((item) => (item.id === updated.id ? updated : item)) : [updated],
      );
    },
  });
}

export function useDeletePromptMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deletePrompt(id),
    onSuccess: (_result, id) => {
      queryClient.setQueryData<PromptTemplate[]>(['prompts'], (prev) =>
        prev ? prev.filter((item) => item.id !== id) : [],
      );
    },
  });
}

export function useUpdateAllowedModelsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => updateAllowedModels(ids),
    onSuccess: (updated) => {
      queryClient.setQueryData<string[]>(['models', 'allowed'], updated);
    },
  });
}

export function useCreateAppointmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AppointmentRecordPayload) => submitAppointmentRecord(payload),
    onSuccess: (created) => {
      queryClient.setQueryData<ReservationRecord[]>(['appointments'], (prev) => {
        if (!prev) return [created];
        const filtered = prev.filter((item) => item.id !== created.id);
        return [created, ...filtered];
      });
    },
  });
}
