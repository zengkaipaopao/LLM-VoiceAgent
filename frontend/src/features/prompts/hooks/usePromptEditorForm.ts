import { useEffect, useState } from 'react';

import { createPrompt, fetchModels, updatePrompt } from '../../../api/prompts';
import { PromptFormValues, PromptTemplate } from '../../../types/shared';
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
  models: string[];
  loadingModels: boolean;
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
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
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
        }
      } catch (error) {
        console.error('Failed to fetch models', error);
        if (!cancelled) {
          setModels([]);
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
    isEditMode,
    handleChange,
    handleSave,
  };
}
