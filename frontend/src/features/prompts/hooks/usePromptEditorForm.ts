import { useEffect, useState } from 'react';

import { createPrompt, fetchModels, updatePrompt } from '../../../api/prompts';
import { LlmModelOption, PromptFormValues, PromptTemplate } from '../../../types/shared';
import {
  buildPromptFormValues,
  defaultPromptFormValues,
} from '../constants/promptEditorDefaults';

interface UsePromptEditorFormArgs {
  open: boolean;
  prompt?: PromptTemplate;
  onClose: () => void;
  onSave: () => void;
}

export interface UsePromptEditorFormResult {
  form: PromptFormValues;
  saving: boolean;
  models: LlmModelOption[];
  loadingModels: boolean;
  modelLoadError: string | null;
  isEditMode: boolean;
  handleChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  handleSave: () => Promise<void>;
}

function isValidJsonSchemaInput(value: string | undefined): boolean {
  if (!value || !value.trim()) {
    return true;
  }
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}

export function usePromptEditorForm({
  open,
  prompt,
  onClose,
  onSave,
}: UsePromptEditorFormArgs): UsePromptEditorFormResult {
  const [form, setForm] = useState<PromptFormValues>({ ...defaultPromptFormValues });
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<LlmModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);
  const isEditMode = !!prompt;

  useEffect(() => {
    setForm(buildPromptFormValues(prompt));
  }, [prompt, open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    let cancelled = false;
    const loadModels = async () => {
      const provider = form.llmProvider || 'gemini';
      setLoadingModels(true);
      try {
        const fetchedModels = await fetchModels(provider);
        if (!cancelled) {
          setModels(fetchedModels);
          setModelLoadError(null);
        }
      } catch (error) {
        console.error('Failed to fetch models', error);
        if (!cancelled) {
          setModels([]);
          setModelLoadError(error instanceof Error ? error.message : String(error));
        }
      } finally {
        if (!cancelled) {
          setLoadingModels(false);
        }
      }
    };

    void loadModels();
    return () => {
      cancelled = true;
    };
  }, [form.llmProvider, open]);

  const handleChange = <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!isValidJsonSchemaInput(form.outputSchema)) {
      alert('Output JSON Schema is invalid JSON.');
      return;
    }

    if (!isValidJsonSchemaInput(form.extractionSchema)) {
      alert('Extraction JSON Schema is invalid JSON.');
      return;
    }

    setSaving(true);
    try {
      if (prompt) {
        await updatePrompt(prompt.id, form);
      } else {
        await createPrompt(form);
      }
      onSave();
      onClose();
    } catch (error) {
      console.error('Failed to save prompt', error);
      alert('Failed to save prompt. Check console for details.');
    } finally {
      setSaving(false);
    }
  };

  return {
    form,
    saving,
    models,
    loadingModels,
    modelLoadError,
    isEditMode,
    handleChange,
    handleSave,
  };
}
