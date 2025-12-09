import { useCallback } from 'react';

import { CreateModelPayload, ModelInfo } from '../../types';
import {
  createCustomModel as createCustomModelApi,
  deleteCustomModel as deleteCustomModelApi,
  fetchAllowedModels,
  fetchModels,
  updateAllowedModels as updateAllowedModelsApi,
} from '../../api/models';
import { useAsyncResource } from '../hooks/useAsyncResource';

type ModelState = {
  models: ModelInfo[];
  allowedModels: string[];
};

export function useModelsStore() {
  const loadModelState = useCallback(async () => {
    const [allModels, allowed] = await Promise.all([fetchModels(), fetchAllowedModels()]);
    return { models: allModels, allowedModels: allowed };
  }, []);

  const {
    data: modelState,
    setData: setModelState,
    loading: loadingModels,
  } = useAsyncResource<ModelState>(loadModelState, {
    initialValue: { models: [], allowedModels: [] },
    onError: (error) => console.error('加载模型列表失败', error),
  });

  const updateAllowedModels = useCallback(async (ids: string[]) => {
    const updated = await updateAllowedModelsApi(ids);
    setModelState((prev) => ({ ...prev, allowedModels: updated }));
    return updated;
  }, [setModelState]);

  const createCustomModel = useCallback(async (payload: CreateModelPayload) => {
    const created = await createCustomModelApi(payload);
    setModelState((prev) => ({ ...prev, models: [...prev.models, created] }));
    return created;
  }, [setModelState]);

  const deleteCustomModel = useCallback(async (modelId: string) => {
    await deleteCustomModelApi(modelId);
    setModelState((prev) => ({
      models: prev.models.filter((model) => model.id !== modelId),
      allowedModels: prev.allowedModels.filter((id) => id !== modelId),
    }));
  }, [setModelState]);

  return {
    models: modelState.models,
    allowedModels: modelState.allowedModels,
    loadingModels,
    updateAllowedModels,
    createCustomModel,
    deleteCustomModel,
  };
}
