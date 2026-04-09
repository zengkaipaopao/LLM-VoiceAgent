import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  finalizeTestSession,
  FinalizeTestSessionResponse,
  startTestSession,
  StartTestSessionResponse,
} from '../../../../api/testLab';
import { isLiveModelId } from '../../../../config/llmModels';
import { Message } from '../../../../hooks/useChatStream';
import { UseUnifiedTestLabResult } from '../../../../hooks/unifiedTestLab/hookTypes';
import { streamUnifiedChatResponse } from '../../../../hooks/unifiedTestLab/streaming';
import { resolveErrorMessage } from '../../../../hooks/unifiedTestLab/streamUtils';
import { buildQuickMessages, deriveSessionStatus } from '../../../../hooks/unifiedTestLab/viewModel';
import { usePromptTemplates } from '../../../../hooks/usePromptTemplates';
import { shouldAutoFinalizeByClosingPhrase } from '../../shared/session/closingPhrase';
import { getSessionCloseRequest, resolveTextStreamRuntime } from '../../shared/session/lifecycle';

export function useTextTestSession(): UseUnifiedTestLabResult {
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
  const autoFinalizeInFlightRef = useRef(false);
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
    if (selectedPrompt && isLiveModelId(selectedPrompt.llmModel)) {
      throw new Error(
        t(
          'pages:test.unified.errors.promptModelRequiresVoiceTab',
          'The selected prompt is configured with a live-only model. Please use the voice test tab or change the prompt model.'
        )
      );
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
  }, [callerName, selectedPrompt, selectedPromptCode, t]);

  const handleStartSession = useCallback(async () => {
    const activeSession = sessionRef.current;
    const closeRequest = getSessionCloseRequest(activeSession, finalizeResult, selectedPromptCode);

    if (closeRequest) {
      setIsFinalizing(true);
      setError(null);
      setInfo(null);
      try {
        const closedResult = await finalizeTestSession(closeRequest);
        setFinalizeResult(closedResult);
      } catch (closeError) {
        setError(
          resolveErrorMessage(
            closeError,
            t(
              'pages:test.unified.errors.closeBeforeNewSessionFailed',
              'Failed to close previous session before starting a new one'
            )
          )
        );
        return;
      } finally {
        setIsFinalizing(false);
      }
    }

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
  }, [createSession, finalizeResult, selectedPromptCode, t]);

  const appendErrorMessage = useCallback((message: string) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === 'assistant' && !last.content.trim()) {
        next.pop();
      }

      next.push({
        role: 'assistant',
        content: `❌ ${message}`,
        timestamp: new Date(),
      });
      return next;
    });
  }, []);

  const finalizeSession = useCallback(
    async (activeSession: StartTestSessionResponse, trigger: 'manual' | 'auto') => {
      if (autoFinalizeInFlightRef.current) {
        return;
      }

      autoFinalizeInFlightRef.current = true;
      setIsFinalizing(true);
      setError(null);
      if (trigger === 'manual') {
        setInfo(null);
      }

      try {
        const result = await finalizeTestSession({
          call_id: activeSession.call_id,
          template_code: activeSession.template_code || selectedPromptCode,
          run_extraction: true,
        });

        setFinalizeResult(result);
        if (trigger === 'auto') {
          setInfo(
            result.extraction?.message ||
              t(
                'pages:test.unified.info.autoSessionFinalized',
                'Detected completion phrase. Session auto-finalized and extraction completed.'
              )
          );
        } else {
          setInfo(
            result.extraction?.message ||
              t('pages:test.unified.info.sessionFinalized', 'Session finalized and extraction completed')
          );
        }
      } catch (finalizeError) {
        setError(
          resolveErrorMessage(
            finalizeError,
            t('pages:test.unified.errors.finalizeFailed', 'Failed to finalize session')
          )
        );
      } finally {
        setIsFinalizing(false);
        autoFinalizeInFlightRef.current = false;
      }
    },
    [selectedPromptCode, t]
  );

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
        let lastAssistantContent = '';
        const runtime = resolveTextStreamRuntime(activeSession, selectedPromptCode);

        await streamUnifiedChatResponse({
          callId: runtime.callId,
          message: content,
          templateCode: runtime.templateCode,
          provider: runtime.provider,
          model: runtime.model,
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
            lastAssistantContent = assistantContent;
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

        if (
          activeSession &&
          !finalizeResult &&
          shouldAutoFinalizeByClosingPhrase(lastAssistantContent)
        ) {
          await finalizeSession(activeSession, 'auto');
        }
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
    [appendErrorMessage, createSession, finalizeResult, finalizeSession, isFinalizing, isSending, selectedPromptCode, t]
  );

  const handleFinalize = useCallback(async () => {
    const activeSession = sessionRef.current;
    if (!activeSession) {
      setError(t('pages:test.unified.errors.noActiveSession', 'Please create a test session first'));
      return;
    }

    await finalizeSession(activeSession, 'manual');
  }, [finalizeSession, t]);

  const handleClear = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    const activeSession = sessionRef.current;
    const closeRequest = getSessionCloseRequest(activeSession, finalizeResult, selectedPromptCode);

    if (closeRequest) {
      setIsFinalizing(true);
      setError(null);
      setInfo(null);
      try {
        await finalizeTestSession(closeRequest);
      } catch (closeError) {
        setError(
          resolveErrorMessage(
            closeError,
            t(
              'pages:test.unified.errors.clearRequiresClose',
              'Failed to close current session. Please try again.'
            )
          )
        );
        return;
      } finally {
        setIsFinalizing(false);
      }
    }

    setSession(null);
    sessionRef.current = null;
    setMessages([]);
    setTotalTokens(0);
    setFinalizeResult(null);
    setError(null);
    setInfo(null);
    autoFinalizeInFlightRef.current = false;
  }, [finalizeResult, selectedPromptCode, t]);

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

export const useUnifiedTestLab = useTextTestSession;
