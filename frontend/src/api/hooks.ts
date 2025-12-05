import { useQuery } from '@tanstack/react-query';
import { http } from './http';
import { CallLog, ModelInfo } from '../types';
import { fetchPrompts } from './prompts';

type PaginatedResponse<T> = {
  data: T[];
  total: number;
};

export function useCalls() {
  return useQuery({
    queryKey: ['calls'],
    queryFn: async () => {
      const response = await http.get<PaginatedResponse<CallLog>>('/calls');
      return response.data;
    },
    staleTime: 30_000,
  });
}

export function usePrompts() {
  return useQuery({
    queryKey: ['prompts'],
    queryFn: fetchPrompts,
  });
}

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await http.get<ModelInfo[]>('/models');
      return response.data;
    },
    staleTime: 60_000,
  });
}
