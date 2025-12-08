import { useCallback, useEffect, useState } from 'react';

import { CreateModelPayload, ModelInfo } from '../../types';
import {
  createCustomModel as createCustomModelApi,
  deleteCustomModel as deleteCustomModelApi,
  fetchAllowedModels,
  fetchModels,
  updateAllowedModels as updateAllowedModelsApi,
} from '../../api/models';

export function useModelsStore() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const loadModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const [allModels, allowed] = await Promise.all([fetchModels(), fetchAllowedModels()]);
      setModels(allModels);
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
    void loadModels();
  }, [loadModels]);

  const updateAllowedModels = useCallback(async (ids: string[]) => {
    const updated = await updateAllowedModelsApi(ids);
    setAllowedModels(updated);
    return updated;
  }, []);

  const createCustomModel = useCallback(async (payload: CreateModelPayload) => {
    const created = await createCustomModelApi(payload);
    setModels((prev) => [...prev, created]);
    return created;
  }, []);

  const deleteCustomModel = useCallback(async (modelId: string) => {
    await deleteCustomModelApi(modelId);
    setModels((prev) => prev.filter((model) => model.id !== modelId));
    setAllowedModels((prev) => prev.filter((id) => id !== modelId));
  }, []);

  return {
    models,
    allowedModels,
    loadingModels,
    updateAllowedModels,
    createCustomModel,
    deleteCustomModel,
  };
}
