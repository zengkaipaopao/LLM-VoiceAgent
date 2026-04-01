import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  finalizeTestSession,
  FinalizeTestSessionResponse,
  startTestSession,
  StartTestSessionResponse,
} from '../api/testLab';
import { Message } from './useChatStream';
import { UseUnifiedTestLabResult } from './unifiedTestLab/hookTypes';
import { streamUnifiedChatResponse } from './unifiedTestLab/streaming';
import { resolveErrorMessage } from './unifiedTestLab/streamUtils';
import { buildQuickMessages, deriveSessionStatus } from './unifiedTestLab/viewModel';
import { usePromptTemplates } from './usePromptTemplates';

export function useUnifiedTestLab(): UseUnifiedTestLabResult {
  const { t } = useTranslation(['pages']);

  const [callerName, setCallerName] = useState('Test Caller');
  const [session, setSession] = useState<StartTestSessionResponse | null>(null);
  const sessionRef = useRef<StartTestSessionResponse | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [totalTokens, setTotalTokens] = useState(0);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeTestSessionResponse | null>(null);

  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const handlePromptLoadError = useCallback(
    (loadError: unknown) => {
      setError(
        t(
          'pages:test.unified.errors.loadPrompts',
          'Failed to load prompt list. Please check backend connection.'
        )
      );
      console.error(loadError);
    },
    [t]
  );
  const { prompts, loadingPrompts, selectedPromptCode, setSelectedPromptCode } = usePromptTemplates({
    preferredCode: 'base_appointment',
    onError: handlePromptLoadError,
  });
  const activeTemplateCode = session?.template_code || selectedPromptCode;
  const selectedPrompt = prompts.find((item) => item.code === activeTemplateCode);
  const quickMessages = useMemo(
    () => buildQuickMessages((key, fallback) => t(key, fallback)),
    [t]
  );

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const createSession = useCallback(async () => {
    if (!selectedPromptCode) {
      throw new Error(t('pages:test.unified.errors.noPromptSelected', 'Please select a prompt first'));
    }

    setIsStarting(true);
    setError(null);
    setInfo(null);

    try {
      const created = await startTestSession({
        template_code: selectedPromptCode,
        caller_name: callerName.trim() || undefined,
      });

      setSession(created);
      sessionRef.current = created;
      setMessages([]);
      setTotalTokens(0);
      setFinalizeResult(null);
      setInfo(
        t('pages:test.unified.info.sessionCreated', 'Test session created: {{phone}}', {
          phone: created.simulated_phone,
        })
      );

      return created;
    } finally {
      setIsStarting(false);
    }
  }, [callerName, selectedPromptCode, t]);

  const handleStartSession = useCallback(async () => {
    try {
      await createSession();
    } catch (startError) {
      setError(
        resolveErrorMessage(
          startError,
          t('pages:test.unified.errors.createSessionFailed', 'Failed to create session')
        )
      );
    }
  }, [createSession, t]);

  const appendErrorMessage = useCallback((message: string) => {
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: `❌ ${message}`,
        timestamp: new Date(),
      },
    ]);
  }, []);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (isSending || isFinalizing) {
        return;
      }

      let activeSession = sessionRef.current;
      try {
        setError(null);
        setInfo(null);

        if (!activeSession) {
          activeSession = await createSession();
        }

        setIsSending(true);

        const userMessage: Message = {
          role: 'user',
          content,
          timestamp: new Date(),
        };

        const assistantMessage: Message = {
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage, assistantMessage]);

        abortControllerRef.current = new AbortController();

        await streamUnifiedChatResponse({
          callId: activeSession.call_id,
          message: content,
          templateCode: activeSession.template_code || selectedPromptCode,
          signal: abortControllerRef.current.signal,
          requestFailedWithStatusMessage: (status: number) =>
            t('pages:test.unified.errors.requestFailedWithStatus', 'Request failed: {{status}}', {
              status,
            }),
          streamFailedMessage: t('pages:test.unified.errors.streamFailed', 'Streaming response failed'),
          onSessionCallId: (callId: string) => {
            if (!activeSession) return;
            const updatedSession = {
              ...activeSession,
              call_id: callId,
            };
            activeSession = updatedSession;
            setSession(updatedSession);
            sessionRef.current = updatedSession;
          },
          onAssistantContent: (assistantContent: string) => {
            setMessages((prev) => {
              const next = [...prev];
              if (next.length > 0) {
                next[next.length - 1] = {
                  ...assistantMessage,
                  content: assistantContent,
                };
              }
              return next;
            });
          },
          onTokensUsed: (tokensUsed: number) => {
            setTotalTokens((prev) => prev + tokensUsed);
          },
        });
      } catch (sendError) {
        if ((sendError as { name?: string })?.name !== 'AbortError') {
          const message = resolveErrorMessage(
            sendError,
            t('pages:test.unified.errors.sendMessageFailed', 'Failed to send message')
          );
          setError(message);
          appendErrorMessage(message);
        }
      } finally {
        setIsSending(false);
        abortControllerRef.current = null;
      }
    },
    [appendErrorMessage, createSession, isFinalizing, isSending, selectedPromptCode, t]
  );

  const handleFinalize = useCallback(async () => {
    const activeSession = sessionRef.current;
    if (!activeSession) {
      setError(t('pages:test.unified.errors.noActiveSession', 'Please create a test session first'));
      return;
    }

    setIsFinalizing(true);
    setError(null);
    setInfo(null);

    try {
      const result = await finalizeTestSession({
        call_id: activeSession.call_id,
        template_code: activeSession.template_code || selectedPromptCode,
        run_extraction: true,
      });

      setFinalizeResult(result);
      setInfo(
        result.extraction?.message ||
          t('pages:test.unified.info.sessionFinalized', 'Session finalized and extraction completed')
      );
    } catch (finalizeError) {
      setError(
        resolveErrorMessage(
          finalizeError,
          t('pages:test.unified.errors.finalizeFailed', 'Failed to finalize session')
        )
      );
    } finally {
      setIsFinalizing(false);
    }
  }, [selectedPromptCode, t]);

  const handleClear = useCallback(() => {
    setMessages([]);
    setTotalTokens(0);
    setFinalizeResult(null);
    setError(null);
    setInfo(null);
  }, []);

  const { sessionClosed, sessionStatus } = useMemo(
    () =>
      deriveSessionStatus({ session, finalizeResult }, (key, fallback) =>
        t(key, fallback)
      ),
    [finalizeResult, session, t]
  );

  return {
    prompts,
    loadingPrompts,
    selectedPromptCode,
    setSelectedPromptCode,
    callerName,
    setCallerName,
    session,
    messages,
    totalTokens,
    finalizeResult,
    isStarting,
    isSending,
    isFinalizing,
    error,
    setError,
    info,
    setInfo,
    selectedPrompt,
    quickMessages,
    sessionClosed,
    sessionStatus,
    handleStartSession,
    handleSendMessage,
    handleFinalize,
    handleClear,
  };
}
