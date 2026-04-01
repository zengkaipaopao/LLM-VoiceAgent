import { useCallback, useRef, useState } from 'react';

import {
  createAssistantErrorMessage,
  createAssistantMessage,
  createUserMessage,
  removeTrailingEmptyAssistantMessage,
  replaceLastMessage,
} from './chatStream/messages';
import { streamChatResponse } from './chatStream/streaming';
import type { ChatRequest, Message, UseChatStreamReturn } from './chatStream/types';

export type { Message } from './chatStream/types';

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return 'Failed to send message';
}

export function useChatStream(
  defaultProvider?: string,
  defaultTemplate: string = 'general_appointment'
): UseChatStreamReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState<string | null>(null);
  const [totalTokens, setTotalTokens] = useState(0);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastOptionsRef = useRef<Partial<ChatRequest>>({});

  const sendMessage = useCallback(
    async (content: string, options: Partial<ChatRequest> = {}) => {
      lastOptionsRef.current = options;
      setError(null);
      setIsLoading(true);

      const userMessage = createUserMessage(content);
      setMessages((prev) => [...prev, userMessage]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const requestBody: ChatRequest = {
        message: content,
        template_code: options.template_code || defaultTemplate,
        provider: options.provider ?? defaultProvider,
        model: options.model,
        temperature: options.temperature,
        call_id: options.call_id || callId || undefined,
      };

      const assistantSeed = createAssistantMessage();
      setMessages((prev) => [...prev, assistantSeed]);

      try {
        await streamChatResponse({
          requestBody,
          signal: controller.signal,
          onCallId: (nextCallId) => {
            setCallId(nextCallId);
          },
          onAssistantContent: (assistantContent) => {
            setMessages((prev) =>
              replaceLastMessage(prev, {
                ...assistantSeed,
                content: assistantContent,
              })
            );
          },
          onTokensUsed: (tokensUsed) => {
            setTotalTokens((prev) => prev + tokensUsed);
          },
        });
      } catch (streamError) {
        if (!isAbortError(streamError)) {
          const errorMessage = resolveErrorMessage(streamError);
          setError(errorMessage);
          setMessages((prev) => [
            ...removeTrailingEmptyAssistantMessage(prev),
            createAssistantErrorMessage(errorMessage),
          ]);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [callId, defaultProvider, defaultTemplate]
  );

  const retryLastMessage = useCallback(async () => {
    const lastUserMessage = messages.slice().reverse().find((message) => message.role === 'user');
    if (!lastUserMessage) {
      return;
    }

    setMessages((prev) => {
      const next = [...prev];
      if (next.length > 0 && next[next.length - 1].role === 'assistant') {
        next.pop();
      }
      if (next.length > 0 && next[next.length - 1].role === 'user') {
        next.pop();
      }
      return next;
    });

    await sendMessage(lastUserMessage.content, lastOptionsRef.current);
  }, [messages, sendMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setCallId(null);
    setError(null);
    setTotalTokens(0);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  const dismissError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    sendMessage,
    retryLastMessage,
    dismissError,
    clearMessages,
  };
}
