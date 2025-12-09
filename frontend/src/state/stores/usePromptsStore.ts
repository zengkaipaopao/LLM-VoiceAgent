import { useCallback } from 'react';

import { PromptFormValues, PromptTemplate } from '../../types';
import {
  createPrompt as createPromptApi,
  deletePrompt as deletePromptApi,
  fetchPrompts,
  updatePrompt as updatePromptApi,
} from '../../api/prompts';
import { useAsyncResource } from '../hooks/useAsyncResource';

export function usePromptsStore() {
  const {
    data: prompts,
    setData: setPrompts,
    loading: loadingPrompts,
  } = useAsyncResource<PromptTemplate[]>(fetchPrompts, {
    initialValue: [],
    onError: (error) => console.error('加载 Prompt 配置失败', error),
  });

  const updatePromptTemplate = useCallback(async (id: string, patch: Partial<PromptTemplate>) => {
    const updated = await updatePromptApi(id, patch);
    setPrompts((prev) => prev.map((prompt) => (prompt.id === id ? updated : prompt)));
    return updated;
  }, [setPrompts]);

  const createPromptTemplate = useCallback(async (payload: PromptFormValues) => {
    const created = await createPromptApi(payload);
    setPrompts((prev) => [...prev, created]);
    return created;
  }, [setPrompts]);

  const deletePromptTemplate = useCallback(async (promptId: string) => {
    await deletePromptApi(promptId);
    setPrompts((prev) => prev.filter((prompt) => prompt.id !== promptId));
  }, [setPrompts]);

  return {
    prompts,
    loadingPrompts,
    updatePromptTemplate,
    createPromptTemplate,
    deletePromptTemplate,
  };
}
