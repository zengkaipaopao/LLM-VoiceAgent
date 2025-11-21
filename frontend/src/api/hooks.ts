import { useQuery } from '@tanstack/react-query';
import { http } from './http';
import { CallLog, PromptTemplate } from '../types';

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
    queryFn: async () => {
      const response = await http.get<PromptTemplate[]>('/prompts');
      return response.data;
    },
  });
}
