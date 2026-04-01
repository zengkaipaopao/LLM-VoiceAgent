import { useEffect, useMemo, useState } from 'react';

import { fetchPrompts } from '../api/prompts';
import { PromptTemplate } from '../types/shared';

interface UsePromptTemplatesOptions {
  preferredCode?: string;
  onError?: (error: unknown) => void;
}

interface UsePromptTemplatesResult {
  prompts: PromptTemplate[];
  loadingPrompts: boolean;
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  selectedPrompt: PromptTemplate | undefined;
}

function resolveDefaultPrompt(templates: PromptTemplate[], preferredCode: string | undefined): PromptTemplate {
  const preferred = preferredCode ? templates.find((item) => item.code === preferredCode) : undefined;
  return preferred ?? templates[0];
}

export function usePromptTemplates(
  options: UsePromptTemplatesOptions = {}
): UsePromptTemplatesResult {
  const { preferredCode, onError } = options;

  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [selectedPromptCode, setSelectedPromptCode] = useState('');

  useEffect(() => {
    let cancelled = false;

    const loadPrompts = async () => {
      setLoadingPrompts(true);
      try {
        const templates = await fetchPrompts();
        if (cancelled) return;

        setPrompts(templates);
        if (!templates.length) {
          setSelectedPromptCode('');
          return;
        }

        const defaultPrompt = resolveDefaultPrompt(templates, preferredCode);
        setSelectedPromptCode((prev) => {
          if (prev && templates.some((item) => item.code === prev)) {
            return prev;
          }
          return defaultPrompt.code;
        });
      } catch (error) {
        if (!cancelled) {
          onError?.(error);
        }
      } finally {
        if (!cancelled) {
          setLoadingPrompts(false);
        }
      }
    };

    void loadPrompts();

    return () => {
      cancelled = true;
    };
  }, [onError, preferredCode]);

  const selectedPrompt = useMemo(
    () => prompts.find((item) => item.code === selectedPromptCode),
    [prompts, selectedPromptCode]
  );

  return {
    prompts,
    loadingPrompts,
    selectedPromptCode,
    setSelectedPromptCode,
    selectedPrompt,
  };
}
