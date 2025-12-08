import { useCallback, useEffect, useState } from 'react';

import { PromptFormValues, PromptTemplate } from '../../types';
import {
  createPrompt as createPromptApi,
  deletePrompt as deletePromptApi,
  fetchPrompts,
  updatePrompt as updatePromptApi,
} from '../../api/prompts';

export function usePromptsStore() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(false);

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

  useEffect(() => {
    void loadPrompts();
  }, [loadPrompts]);

  const updatePromptTemplate = useCallback(async (id: string, patch: Partial<PromptTemplate>) => {
    const updated = await updatePromptApi(id, patch);
    setPrompts((prev) => prev.map((prompt) => (prompt.id === id ? updated : prompt)));
    return updated;
  }, []);

  const createPromptTemplate = useCallback(async (payload: PromptFormValues) => {
    const created = await createPromptApi(payload);
    setPrompts((prev) => [...prev, created]);
    return created;
  }, []);

  const deletePromptTemplate = useCallback(async (promptId: string) => {
    await deletePromptApi(promptId);
    setPrompts((prev) => prev.filter((prompt) => prompt.id !== promptId));
  }, []);

  return {
    prompts,
    loadingPrompts,
    updatePromptTemplate,
    createPromptTemplate,
    deletePromptTemplate,
  };
}
