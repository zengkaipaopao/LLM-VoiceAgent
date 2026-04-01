import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchPrompts } from '../api/prompts';
import { Message, useChatStream } from './useChatStream';
import { PromptTemplate } from '../types/shared';

interface UseChatInterfaceStateArgs {
  defaultTemplate: string;
}

interface UseChatInterfaceStateResult {
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  selectedPrompt: PromptTemplate | undefined;
  loadingPrompts: boolean;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  callId: string | null;
  totalTokens: number;
  handleSend: (content: string) => Promise<void>;
  handleExport: () => void;
  retryLastMessage: () => Promise<void>;
  dismissError: () => void;
  clearMessages: () => void;
}

export function useChatInterfaceState({
  defaultTemplate,
}: UseChatInterfaceStateArgs): UseChatInterfaceStateResult {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPromptCode, setSelectedPromptCode] = useState(defaultTemplate);
  const [loadingPrompts, setLoadingPrompts] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const loadPrompts = async () => {
      try {
        const data = await fetchPrompts();
        if (cancelled) {
          return;
        }

        setPrompts(data);
        if (data.length > 0 && !data.find((prompt) => prompt.code === defaultTemplate)) {
          setSelectedPromptCode(data[0].code);
        }
      } catch (error) {
        console.error('Failed to load prompts', error);
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
  }, [defaultTemplate]);

  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.code === selectedPromptCode),
    [prompts, selectedPromptCode]
  );

  const {
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    sendMessage,
    retryLastMessage,
    dismissError,
    clearMessages,
  } = useChatStream(undefined, selectedPromptCode);

  const handleSend = useCallback(
    async (content: string) => {
      await sendMessage(content, {
        template_code: selectedPromptCode,
      });
    },
    [selectedPromptCode, sendMessage]
  );

  const handleExport = useCallback(() => {
    const data = {
      call_id: callId,
      agent: selectedPrompt?.name,
      template_code: selectedPromptCode,
      total_tokens: totalTokens,
      messages: messages.map((message) => ({
        role: message.role,
        content: message.content,
        timestamp: message.timestamp.toISOString(),
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `chat-${callId || 'new'}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [callId, messages, selectedPrompt?.name, selectedPromptCode, totalTokens]);

  return {
    prompts,
    selectedPromptCode,
    setSelectedPromptCode,
    selectedPrompt,
    loadingPrompts,
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    handleSend,
    handleExport,
    retryLastMessage,
    dismissError,
    clearMessages,
  };
}
