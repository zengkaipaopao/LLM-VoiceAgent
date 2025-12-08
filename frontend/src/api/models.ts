import { http } from './http';
import { CreateModelPayload, ModelInfo } from '../types';

export async function fetchModels() {
  const response = await http.get<ModelInfo[]>('/models');
  return response.data;
}

export async function fetchAllowedModels() {
  const response = await http.get<string[]>('/models/allowed');
  return response.data;
}

export async function updateAllowedModels(ids: string[]) {
  const response = await http.put<string[]>('/models/allowed', { ids });
  return response.data;
}

export async function createCustomModel(payload: CreateModelPayload) {
  const response = await http.post<ModelInfo>('/models/custom', payload);
  return response.data;
}

export async function deleteCustomModel(modelId: string) {
  await http.delete(`/models/custom/${encodeURIComponent(modelId)}`);
}
