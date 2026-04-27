import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  GoogleGenAI,
  Modality,
  type LiveConnectConfig,
  type LiveServerMessage,
  type Session,
} from '@google/genai';

import { fetchLiveAuthToken } from '../../../../api/live';
import {
  appendTestSessionMessages,
  finalizeTestSession,
  processTestSessionOperationTurn,
  startTestSession,
  type FinalizeTestSessionResponse,
  type StartTestSessionResponse,
} from '../../../../api/testLab';
import { DEFAULT_LIVE_MODEL, isLiveModelId } from '../../../../config/llmModels';
import { PromptTemplate } from '../../../../types/shared';
import { appendEventLog, EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';
import { handleLiveEventPayload } from '../../../../hooks/liveConsole/eventHandlers';
import { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
import { useMicrophoneStream } from '../../../../hooks/liveConsole/useMicrophoneStream';
import { useRemoteAudioPlayback } from '../../../../hooks/liveConsole/useRemoteAudioPlayback';
import { usePromptTemplates } from '../../../../hooks/usePromptTemplates';
import { shouldAutoFinalizeByClosingPhrase } from '../../shared/session/closingPhrase';

export type { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
export type { EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';

const DEFAULT_DISPLAY_ENDPOINT = 'Gemini Live client-to-server (ephemeral token)';

type PersistableMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export interface UseLiveWebSocketConsoleResult {
  socketStatus: SocketStatus;
  wsOpen: boolean;
  micStatus: MicStatus;
  error: string | null;
  setError: (value: string | null) => void;
  info: string | null;
  setInfo: (value: string | null) => void;
  model: string;
  setModel: (value: string) => void;
  modalities: string;
  setModalities: (value: string) => void;
  voice: string;
  setVoice: (value: string) => void;
  systemInstruction: string;
  setSystemInstruction: (value: string) => void;
  prompts: PromptTemplate[];
  loadingPrompts: boolean;
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  textInput: string;
  setTextInput: (value: string) => void;
  sessionId: string;
  assistantText: string;
  inputTranscript: string;
  outputTranscript: string;
  totalTokens: number;
  logs: EventLog[];
  displayWsUrl: string;
  testCallId: string;
  finalizeResult: FinalizeTestSessionResponse | null;
  canUseRealtimeInput: boolean;
  voiceOnlyMode: boolean;
  connectSocket: () => void;
  disconnectSocket: () => void;
  clearConsole: () => void;
  sendText: () => void;
  toggleMicrophone: (enabled: boolean) => void;
}

function mergeTranscriptChunk(current: string, incomingRaw: string): string {
  const incoming = incomingRaw.trim();
  if (!incoming) {
    return current;
  }
  if (!current) {
    return incoming;
  }
  if (incoming === current) {
    return current;
  }
  if (incoming.startsWith(current)) {
    return incoming;
  }
  if (current.startsWith(incoming)) {
    return current;
  }
  if (current.endsWith(incoming)) {
    return current;
  }
  return `${current} ${incoming}`.trim();
}

function parseResponseModalities(raw: string): Modality[] {
  const tokens = raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);

  if (!tokens.length) {
    return [Modality.AUDIO];
  }

  const mapped = tokens.flatMap((token) => {
    if (token === 'AUDIO') return [Modality.AUDIO];
    if (token === 'TEXT') return [Modality.TEXT];
    return [];
  });

  return mapped.length ? mapped : [Modality.AUDIO];
}

function buildBrowserLiveConfig(params: {
  modalities: string;
  voice?: string;
  systemInstruction?: string | null;
}): LiveConnectConfig {
  const config: LiveConnectConfig = {
    responseModalities: parseResponseModalities(params.modalities),
    inputAudioTranscription: {},
    outputAudioTranscription: {},
  };

  const voice = (params.voice || '').trim();
  if (voice) {
    config.speechConfig = {
      voiceConfig: {
        prebuiltVoiceConfig: {
          voiceName: voice,
        },
      },
    };
  }

  const instruction = (params.systemInstruction || '').trim();
  if (instruction) {
    config.systemInstruction = instruction;
  }

  return config;
}

function normalizeLiveServerMessage(message: LiveServerMessage): LiveEventPayload[] {
  const payloads: LiveEventPayload[] = [];

  if (message.setupComplete?.sessionId) {
    payloads.push({ type: 'session_ready', session_id: message.setupComplete.sessionId });
  }

  if (message.usageMetadata) {
    payloads.push({
      type: 'usage',
      total_tokens: message.usageMetadata.totalTokenCount ?? 0,
    });
  }

  const content = message.serverContent;
  if (content?.inputTranscription?.text) {
    payloads.push({
      type: 'input_transcript',
      text: content.inputTranscription.text,
      final: Boolean(content.inputTranscription.finished),
    });
  }

  if (content?.outputTranscription?.text) {
    payloads.push({
      type: 'output_transcript',
      text: content.outputTranscription.text,
      final: Boolean(content.outputTranscription.finished),
    });
  }

  if (content?.modelTurn?.parts) {
    for (const part of content.modelTurn.parts) {
      if (part.text) {
        payloads.push({ type: 'text', text: part.text });
      }
      if (part.inlineData?.data) {
        payloads.push({
          type: 'audio_chunk',
          data: part.inlineData.data,
          mime_type: part.inlineData.mimeType,
        });
      }
    }
  }

  if (content?.interrupted) {
    payloads.push({ type: 'interrupted' });
  }

  if (content?.turnComplete) {
    payloads.push({
      type: 'turn_complete',
      reason: content.turnCompleteReason ?? null,
    });
  }

  if (message.goAway?.timeLeft) {
    payloads.push({
      type: 'warning',
      message: `Gemini Live asked the client to reconnect soon. time_left=${message.goAway.timeLeft}`,
    });
  }

  return payloads;
}

export function useVoiceTestConsole(): UseLiveWebSocketConsoleResult {
  const { t } = useTranslation(['pages']);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>('disconnected');
  const [wsOpen, setWsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [model, setModel] = useState(DEFAULT_LIVE_MODEL);
  const [modalities, setModalities] = useState('AUDIO');
  const [voice, setVoice] = useState('');
  const [systemInstruction, setSystemInstruction] = useState(
    'You are a helpful bilingual voice assistant for customer service.'
  );
  const [textInput, setTextInput] = useState('');
  const [displayWsUrl, setDisplayWsUrl] = useState(DEFAULT_DISPLAY_ENDPOINT);

  const [sessionId, setSessionId] = useState<string>('');
  const [assistantText, setAssistantText] = useState('');
  const [inputTranscript, setInputTranscript] = useState('');
  const [outputTranscript, setOutputTranscript] = useState('');
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [testSession, setTestSession] = useState<StartTestSessionResponse | null>(null);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeTestSessionResponse | null>(null);
  const voiceOnlyMode = true;

  const sessionRef = useRef<Session | null>(null);
  const testSessionRef = useRef<StartTestSessionResponse | null>(null);
  const inputTranscriptHistoryRef = useRef('');
  const inputTranscriptTurnRef = useRef('');
  const outputTranscriptHistoryRef = useRef('');
  const outputTranscriptTurnRef = useRef('');
  const queuedPersistMessagesRef = useRef<PersistableMessage[]>([]);
  const appendRequestChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const lastLoggedInputRef = useRef('');
  const lastLoggedOutputRef = useRef('');
  const lastCompletedAssistantTurnRef = useRef('');
  const lastLoadedPromptLogRef = useRef('');
  const lastTextSendRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });
  const isManualDisconnectRef = useRef(false);
  const finalizeInFlightRef = useRef(false);
  const autoFinalizeTriggeredRef = useRef(false);
  const suppressGeminiTurnRef = useRef(false);

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((prev) => appendEventLog(prev, level, message, 180));
  }, []);

  const queuePersistableMessage = useCallback((role: 'user' | 'assistant', content: string) => {
    const normalized = content.trim();
    if (!normalized) {
      return;
    }
    queuedPersistMessagesRef.current.push({ role, content: normalized });
  }, []);

  const flushPersistedMessages = useCallback(async () => {
    const activeSession = testSessionRef.current;
    if (!activeSession) {
      return;
    }

    const entries = queuedPersistMessagesRef.current.splice(0);
    if (!entries.length) {
      return;
    }

    const task = appendTestSessionMessages({
      call_id: activeSession.call_id,
      template_code: activeSession.template_code || undefined,
      provider: activeSession.llm_provider,
      model: activeSession.llm_model,
      messages: entries,
    }).catch((persistError) => {
      queuedPersistMessagesRef.current = [...entries, ...queuedPersistMessagesRef.current];
      pushLog(
        'error',
        t(
          'pages:test.voiceLab.direct.logs.persistTranscriptFailed',
          'Failed to persist the voice test transcript: {{message}}',
          {
            message: persistError instanceof Error ? persistError.message : String(persistError),
          }
        )
      );
    });

    appendRequestChainRef.current = appendRequestChainRef.current.then(() => task);
    await appendRequestChainRef.current;
  }, [pushLog, t]);

  const finalizeActiveTestSession = useCallback(
    async (runExtraction: boolean) => {
      const activeSession = testSessionRef.current;
      if (!activeSession || finalizeInFlightRef.current) {
        return null;
      }

      finalizeInFlightRef.current = true;
      try {
        const result = await finalizeTestSession({
          call_id: activeSession.call_id,
          template_code: activeSession.template_code || undefined,
          run_extraction: runExtraction,
        });
        setFinalizeResult(result);
        setInfo(
          runExtraction
            ? result.extraction?.message ||
                t(
                  'pages:test.voiceLab.direct.info.sessionFinalizedWithExtraction',
                  'The voice test session has ended and appointment extraction is complete.'
                )
            : t('pages:test.voiceLab.direct.info.sessionFinalized', 'The voice test session has ended.')
        );
        return result;
      } catch (finalizeError) {
        const message =
          finalizeError instanceof Error ? finalizeError.message : String(finalizeError);
        setError(message);
        pushLog(
          'error',
          t('pages:test.voiceLab.direct.logs.finalizeFailed', 'Failed to finalize voice test session: {{message}}', {
            message,
          })
        );
        return null;
      } finally {
        finalizeInFlightRef.current = false;
      }
    },
    [pushLog, t]
  );

  const handlePromptLoadError = useCallback(
    (loadError: unknown) => {
      pushLog(
        'error',
        t('pages:test.voiceLab.direct.logs.promptLoadFailed', 'Failed to load prompts: {{message}}', {
          message: String(loadError),
        })
      );
    },
    [pushLog, t]
  );

  const { prompts, loadingPrompts, selectedPromptCode, setSelectedPromptCode } = usePromptTemplates({
    preferredCode: 'base_appointment',
    onError: handlePromptLoadError,
  });

  useEffect(() => {
    testSessionRef.current = testSession;
  }, [testSession]);

  const { playPcmAudioChunk, isRemotePlaybackActive, resetRemotePlayback } = useRemoteAudioPlayback({ pushLog });

  const canSendRealtimeInput = useCallback(() => Boolean(sessionRef.current) && socketStatus === 'connected', [socketStatus]);

  const sendAudioChunk = useCallback(({ mimeType, data }: { mimeType: string; data: string }) => {
    sessionRef.current?.sendRealtimeInput({
      audio: {
        mimeType,
        data,
      },
    });
  }, []);

  const sendAudioStreamEnd = useCallback(() => {
    sessionRef.current?.sendRealtimeInput({
      audioStreamEnd: true,
    });
  }, []);

  const {
    micStatus,
    stopMicrophone,
    resetMicrophone,
    toggleMicrophone,
    hasActiveMicrophoneResources,
  } = useMicrophoneStream({
    canSendRealtimeInput,
    sendAudioChunk,
    sendAudioStreamEnd,
    isRemotePlaybackActive,
    pushLog,
    setError,
  });

  const canUseRealtimeInput = wsOpen && socketStatus === 'connected';

  const closeDirectTransport = useCallback(
    (logMessage: string) => {
      isManualDisconnectRef.current = true;
      if (hasActiveMicrophoneResources()) {
        stopMicrophone();
      }
      sessionRef.current?.close();
      sessionRef.current = null;
      setSocketStatus('disconnected');
      setWsOpen(false);
      setSessionId('');
      resetRemotePlayback();
      pushLog('info', logMessage);
    },
    [hasActiveMicrophoneResources, pushLog, resetRemotePlayback, stopMicrophone]
  );

  useEffect(() => {
    if (!voiceOnlyMode) return;
    if (modalities === 'AUDIO') return;
    setModalities('AUDIO');
  }, [modalities, voiceOnlyMode]);

  useEffect(() => {
    if (!voiceOnlyMode) return;
    if (selectedPromptCode) return;
    if (!prompts.length) return;
    setSelectedPromptCode(prompts[0].code);
  }, [prompts, selectedPromptCode, setSelectedPromptCode, voiceOnlyMode]);

  useEffect(() => {
    if (!voiceOnlyMode) return;
    if (!textInput) return;
    setTextInput('');
  }, [textInput, voiceOnlyMode]);

  const appendAssistantText = useCallback((value: string) => {
    if (value === '\n') {
      setAssistantText((prev) => (prev.endsWith('\n') ? prev : `${prev}\n`));
      return;
    }
    setAssistantText((prev) => prev + value);
  }, []);

  const appendBackendAssistantTurn = useCallback(
    (value: string) => {
      const finalized = value.trim();
      if (!finalized) {
        return;
      }

      setAssistantText((prev) => {
        if (!prev) {
          return `${finalized}\n`;
        }
        return prev.endsWith('\n') ? `${prev}${finalized}\n` : `${prev}\n${finalized}\n`;
      });

      const nextHistory = `${outputTranscriptHistoryRef.current}${finalized}\n`;
      outputTranscriptHistoryRef.current = nextHistory;
      outputTranscriptTurnRef.current = '';
      setOutputTranscript(nextHistory);

      if (lastLoggedOutputRef.current !== finalized) {
        pushLog(
          'success',
          t('pages:test.voiceLab.direct.logs.operationAssistantTurn', 'AI (business flow): {{text}}', {
            text: finalized,
          })
        );
        lastLoggedOutputRef.current = finalized;
      }
      lastCompletedAssistantTurnRef.current = finalized;
    },
    [pushLog]
  );

  const processOperationFlowTurn = useCallback(
    async (finalizedUserTurn: string) => {
      const activeSession = testSessionRef.current;
      if (!activeSession) {
        return false;
      }

      await flushPersistedMessages();

      try {
        const result = await processTestSessionOperationTurn({
          call_id: activeSession.call_id,
          message: finalizedUserTurn,
          template_code: activeSession.template_code || undefined,
          provider: activeSession.llm_provider,
          model: activeSession.llm_model,
        });
        if (!result.handled || !result.response) {
          return false;
        }

          suppressGeminiTurnRef.current = true;
        appendBackendAssistantTurn(result.response);
        if (result.executed) {
          setInfo(
            t(
              'pages:test.voiceLab.direct.info.operationCompleted',
              'The appointment {{operation}} was completed through the business state machine.',
              {
                operation:
                  result.operation === 'cancel'
                    ? t('pages:test.voiceLab.direct.operation.cancel', 'cancellation')
                    : t('pages:test.voiceLab.direct.operation.update', 'change'),
              }
            )
          );
        } else if (result.operation) {
          setInfo(
            t(
              'pages:test.voiceLab.direct.info.operationEntered',
              'Entered the appointment {{operation}} business flow.',
              {
                operation:
                  result.operation === 'cancel'
                    ? t('pages:test.voiceLab.direct.operation.cancel', 'cancellation')
                    : t('pages:test.voiceLab.direct.operation.update', 'change'),
              }
            )
          );
        }
        pushLog(
          'info',
          t(
            'pages:test.voiceLab.direct.logs.operationFlowHandled',
            'ChatService operation flow handled the turn: operation={{operation}} state={{state}} executed={{executed}}',
            {
              operation: result.operation || '-',
              state: result.state_status || '-',
              executed: result.executed ? 'yes' : 'no',
            }
          )
        );
        return true;
      } catch (operationError) {
        pushLog(
          'error',
          t(
            'pages:test.voiceLab.direct.logs.operationFlowAdvanceFailed',
            'Failed to advance the ChatService operation flow: {{message}}',
            {
              message:
                operationError instanceof Error ? operationError.message : String(operationError),
            }
          )
        );
        return false;
      }
    },
    [appendBackendAssistantTurn, flushPersistedMessages, pushLog, t]
  );

  const appendInputTranscript = useCallback(
    async (chunk: string, isFinal: boolean) => {
      const mergedTurn = mergeTranscriptChunk(inputTranscriptTurnRef.current, chunk);
      if (!mergedTurn) return;

      inputTranscriptTurnRef.current = mergedTurn;
      if (!isFinal) {
        setInputTranscript(`${inputTranscriptHistoryRef.current}${mergedTurn}`);
        return;
      }

      const finalized = mergedTurn.trim();
      const nextHistory = finalized
        ? `${inputTranscriptHistoryRef.current}${finalized}\n`
        : inputTranscriptHistoryRef.current;
      inputTranscriptHistoryRef.current = nextHistory;
      inputTranscriptTurnRef.current = '';
      setInputTranscript(nextHistory);

      if (finalized && lastLoggedInputRef.current !== finalized) {
        pushLog('info', `用户: ${finalized}`);
        lastLoggedInputRef.current = finalized;
      }
      if (finalized) {
        const handledByOperationFlow = await processOperationFlowTurn(finalized);
        if (handledByOperationFlow) {
          return;
        }
        queuePersistableMessage('user', finalized);
      }
    },
    [processOperationFlowTurn, pushLog, queuePersistableMessage]
  );

  const appendOutputTranscript = useCallback(
    (chunk: string, isFinal: boolean) => {
      const mergedTurn = mergeTranscriptChunk(outputTranscriptTurnRef.current, chunk);
      if (!mergedTurn) return;

      outputTranscriptTurnRef.current = mergedTurn;
      if (!isFinal) {
        setOutputTranscript(`${outputTranscriptHistoryRef.current}${mergedTurn}`);
        return;
      }

      const finalized = mergedTurn.trim();
      const nextHistory = finalized
        ? `${outputTranscriptHistoryRef.current}${finalized}\n`
        : outputTranscriptHistoryRef.current;
      outputTranscriptHistoryRef.current = nextHistory;
      outputTranscriptTurnRef.current = '';
      setOutputTranscript(nextHistory);

      if (finalized && lastLoggedOutputRef.current !== finalized) {
        pushLog('success', `AI: ${finalized}`);
        lastLoggedOutputRef.current = finalized;
      }
      if (finalized) {
        lastCompletedAssistantTurnRef.current = finalized;
        queuePersistableMessage('assistant', finalized);
      }
    },
    [pushLog, queuePersistableMessage]
  );

  const flushTranscriptTurns = useCallback(() => {
    const pendingInput = inputTranscriptTurnRef.current.trim();
    if (pendingInput) {
      const nextHistory = `${inputTranscriptHistoryRef.current}${pendingInput}\n`;
      inputTranscriptHistoryRef.current = nextHistory;
      inputTranscriptTurnRef.current = '';
      setInputTranscript(nextHistory);
      if (lastLoggedInputRef.current !== pendingInput) {
        pushLog('info', `用户: ${pendingInput}`);
        lastLoggedInputRef.current = pendingInput;
      }
      queuePersistableMessage('user', pendingInput);
    }

    const pendingOutput = outputTranscriptTurnRef.current.trim();
    if (pendingOutput) {
      const nextHistory = `${outputTranscriptHistoryRef.current}${pendingOutput}\n`;
      outputTranscriptHistoryRef.current = nextHistory;
      outputTranscriptTurnRef.current = '';
      setOutputTranscript(nextHistory);
      if (lastLoggedOutputRef.current !== pendingOutput) {
        pushLog('success', `AI: ${pendingOutput}`);
        lastLoggedOutputRef.current = pendingOutput;
      }
      lastCompletedAssistantTurnRef.current = pendingOutput;
      queuePersistableMessage('assistant', pendingOutput);
    }
  }, [pushLog, queuePersistableMessage]);

  const handlePayload = useCallback(
    async (payload: LiveEventPayload) => {
      const normalizedType = (payload.type || '').toLowerCase();

      if (
        suppressGeminiTurnRef.current &&
        (normalizedType === 'text' ||
          normalizedType === 'output_transcript' ||
          normalizedType === 'audio_chunk')
      ) {
        return;
      }

      await handleLiveEventPayload({
        event: payload,
        setSocketStatus,
        startHeartbeat: () => {
          // The official browser client manages its own connection lifecycle;
          // keep the existing event pipeline but no custom heartbeat is needed.
        },
        pushLog,
        setSessionId,
        appendAssistantText,
        appendInputTranscript,
        appendOutputTranscript,
        flushTranscriptTurns,
        playPcmAudioChunk,
        setTotalTokens,
        setError: (value) => setError(value),
      });

      if (normalizedType === 'turn_complete' || normalizedType === 'interrupted') {
        if (suppressGeminiTurnRef.current) {
          suppressGeminiTurnRef.current = false;
        }
        await flushPersistedMessages();
      }

      if (
        normalizedType === 'turn_complete' &&
        !autoFinalizeTriggeredRef.current &&
        !finalizeResult &&
        shouldAutoFinalizeByClosingPhrase(lastCompletedAssistantTurnRef.current)
      ) {
        autoFinalizeTriggeredRef.current = true;
        pushLog(
          'info',
          t(
            'pages:test.voiceLab.direct.logs.closingPhraseDetected',
            'Detected a closing phrase. Auto-finalizing the voice test session.'
          )
        );
        closeDirectTransport(
          t(
            'pages:test.voiceLab.direct.logs.directSessionAutoClosed',
            'Gemini Live direct session auto-closed after the closing phrase.'
          )
        );
        const result = await finalizeActiveTestSession(true);
        if (result) {
          setInfo(
            result.extraction?.message ||
              t(
                'pages:test.voiceLab.direct.info.autoFinalizedByClosingPhrase',
                'Detected a closing phrase, automatically disconnected the voice session, and completed extraction.'
              )
          );
        }
      }
    },
    [
      closeDirectTransport,
      appendAssistantText,
      appendInputTranscript,
      appendOutputTranscript,
      finalizeActiveTestSession,
      finalizeResult,
      flushPersistedMessages,
      flushTranscriptTurns,
      playPcmAudioChunk,
      pushLog,
    ]
  );

  const clearConsole = useCallback(() => {
    void (async () => {
      const activeSession = testSessionRef.current;
      const hasDialogue = Boolean(
        inputTranscriptHistoryRef.current.trim() ||
          outputTranscriptHistoryRef.current.trim() ||
          queuedPersistMessagesRef.current.length
      );

      if (activeSession && !finalizeResult) {
        await flushPersistedMessages();
        await finalizeActiveTestSession(hasDialogue);
      }

      setAssistantText('');
      setInputTranscript('');
      setOutputTranscript('');
      inputTranscriptHistoryRef.current = '';
      inputTranscriptTurnRef.current = '';
      outputTranscriptHistoryRef.current = '';
      outputTranscriptTurnRef.current = '';
      queuedPersistMessagesRef.current = [];
      lastLoggedInputRef.current = '';
      lastLoggedOutputRef.current = '';
      lastCompletedAssistantTurnRef.current = '';
      lastLoadedPromptLogRef.current = '';
      lastTextSendRef.current = { text: '', ts: 0 };
      autoFinalizeTriggeredRef.current = false;
      suppressGeminiTurnRef.current = false;
      setLogs([]);
      setTotalTokens(0);
      setError(null);
      setInfo(null);
      setTestSession(null);
      setFinalizeResult(null);
    })();
  }, [finalizeActiveTestSession, finalizeResult, flushPersistedMessages]);

  const disconnectSocket = useCallback(() => {
    void (async () => {
      flushTranscriptTurns();
      await flushPersistedMessages();

      const hasDialogue = Boolean(
        inputTranscriptHistoryRef.current.trim() || outputTranscriptHistoryRef.current.trim()
      );

      closeDirectTransport(t('pages:test.voiceLab.direct.logs.directSessionClosed', 'Gemini Live direct session closed.'));
      suppressGeminiTurnRef.current = false;

      await finalizeActiveTestSession(hasDialogue);
    })();
  }, [
    closeDirectTransport,
    finalizeActiveTestSession,
    flushPersistedMessages,
    flushTranscriptTurns,
  ]);

  const connectSocket = useCallback(() => {
    const normalizedModel = model.trim();
    if (!isLiveModelId(normalizedModel)) {
      setError(
        t(
          'pages:test.voiceLab.direct.errors.incompatibleModel',
          'The current model is not a Gemini Live / Native Audio model. Select a voice model in the Prompt or explicitly override it here.'
        )
      );
      pushLog(
        'error',
        t('pages:test.voiceLab.direct.logs.incompatibleModel', 'Incompatible voice test model: {{model}}', {
          model: normalizedModel || '(empty)',
        })
      );
      return;
    }

    void (async () => {
      try {
        isManualDisconnectRef.current = false;
        const previousSession = testSessionRef.current;
        if (previousSession && !finalizeResult) {
          await finalizeActiveTestSession(
            Boolean(inputTranscriptHistoryRef.current.trim() || outputTranscriptHistoryRef.current.trim())
          );
        }
        if (sessionRef.current) {
          sessionRef.current.close();
          sessionRef.current = null;
        }
        if (hasActiveMicrophoneResources()) {
          resetMicrophone();
        }
        resetRemotePlayback();

        setError(null);
        setInfo(null);
        setSocketStatus('connecting');
        setWsOpen(false);
        setAssistantText('');
        setInputTranscript('');
        setOutputTranscript('');
        setTotalTokens(0);
        setSessionId('');
        setDisplayWsUrl(DEFAULT_DISPLAY_ENDPOINT);
        setFinalizeResult(null);
        inputTranscriptHistoryRef.current = '';
        inputTranscriptTurnRef.current = '';
        outputTranscriptHistoryRef.current = '';
        outputTranscriptTurnRef.current = '';
        queuedPersistMessagesRef.current = [];
        lastLoggedInputRef.current = '';
        lastLoggedOutputRef.current = '';
        lastCompletedAssistantTurnRef.current = '';
        lastTextSendRef.current = { text: '', ts: 0 };
        autoFinalizeTriggeredRef.current = false;
        suppressGeminiTurnRef.current = false;

        const createdSession = await startTestSession({
          template_code: selectedPromptCode.trim() || 'base_appointment',
          caller_name: 'Voice Test Caller',
          model: normalizedModel,
          mode: 'voice',
        });
        setTestSession(createdSession);
        pushLog(
          'info',
          t('pages:test.voiceLab.direct.logs.sessionCreated', 'Voice test session created: {{callId}}', {
            callId: createdSession.call_id,
          })
        );

        pushLog(
          'info',
          t('pages:test.voiceLab.direct.logs.requestingEphemeralToken', 'Requesting a Gemini Live ephemeral token...')
        );
        const auth = await fetchLiveAuthToken({
          model: normalizedModel,
          modalities: ['AUDIO'],
          voice: voice.trim() || undefined,
          templateCode: selectedPromptCode.trim() || undefined,
          systemInstruction: selectedPromptCode.trim() ? undefined : systemInstruction.trim() || undefined,
        });

        setDisplayWsUrl(auth.display_endpoint);
        setModel(auth.model);
        setTestSession((previous) =>
          previous
            ? {
                ...previous,
                llm_model: auth.model,
              }
            : previous
        );
        if (!voice.trim() && auth.voice) {
          setVoice(auth.voice);
        }

        const ai = new GoogleGenAI({
          apiKey: auth.auth_token,
          apiVersion: 'v1alpha',
        });
        const config = buildBrowserLiveConfig({
          modalities: auth.modalities.join(','),
          voice: auth.voice ?? undefined,
          systemInstruction: auth.system_instruction,
        });

        const session = await ai.live.connect({
          model: auth.model,
          config,
          callbacks: {
            onopen: () => {
              setWsOpen(true);
              setSocketStatus('connected');
              pushLog('success', t('pages:test.voiceLab.direct.logs.connected', 'Gemini Live direct session connected.'));
            },
            onmessage: (message) => {
              const payloads = normalizeLiveServerMessage(message);
              for (const payload of payloads) {
                void handlePayload(payload);
              }
            },
            onerror: (event) => {
              const message =
                event.message ||
                t('pages:test.voiceLab.direct.errors.connectionErrorFallback', 'Gemini Live direct connection error.');
              setError(message);
              setSocketStatus('error');
              pushLog('error', message);
            },
            onclose: (event) => {
              const detail =
                event.reason && event.reason.length
                  ? t(
                      'pages:test.voiceLab.direct.logs.connectionClosedWithReason',
                      'Gemini Live connection closed (code: {{code}}, reason: {{reason}}).',
                      { code: event.code, reason: event.reason }
                    )
                  : t('pages:test.voiceLab.direct.logs.connectionClosed', 'Gemini Live connection closed (code: {{code}}).', {
                      code: event.code,
                    });
              if (!isManualDisconnectRef.current) {
                pushLog('info', detail);
              }
              sessionRef.current = null;
              setWsOpen(false);
              setSocketStatus('disconnected');
              setSessionId('');
              suppressGeminiTurnRef.current = false;
              if (hasActiveMicrophoneResources()) {
                resetMicrophone();
              }
              resetRemotePlayback();
              isManualDisconnectRef.current = false;
            },
          },
        });

        sessionRef.current = session;
      } catch (connectError) {
        const message = connectError instanceof Error ? connectError.message : String(connectError);
        setError(message);
        setSocketStatus('error');
        setWsOpen(false);
        pushLog(
          'error',
          t('pages:test.voiceLab.direct.logs.connectFailed', 'Failed to connect to Gemini Live directly: {{message}}', {
            message,
          })
        );
      }
    })();
  }, [
    handlePayload,
    hasActiveMicrophoneResources,
    model,
    pushLog,
    resetMicrophone,
    resetRemotePlayback,
    selectedPromptCode,
    systemInstruction,
    t,
    voice,
    finalizeActiveTestSession,
    finalizeResult,
  ]);

  const sendText = useCallback(() => {
    if (voiceOnlyMode) {
      pushLog(
        'warning',
        t('pages:test.voiceLab.direct.logs.voiceOnlyMode', 'Voice-only mode is enabled. Text input is disabled in this tab.')
      );
      return;
    }

    const text = textInput.trim();
    if (!text) return;
    if (!sessionRef.current) {
      setError(t('pages:test.voiceLab.direct.errors.notConnected', 'Gemini Live is not connected.'));
      return;
    }

    const now = Date.now();
    const previous = lastTextSendRef.current;
    if (previous.text === text && now - previous.ts < 1200) {
      pushLog('warning', t('pages:test.voiceLab.direct.logs.duplicateTextIgnored', 'Duplicate text input ignored.'));
      return;
    }
    lastTextSendRef.current = { text, ts: now };

    sessionRef.current.sendClientContent({ turns: text, turnComplete: true });
    pushLog('info', t('pages:test.voiceLab.direct.logs.textInput', 'Text input: {{text}}', { text }));
    setTextInput('');
  }, [pushLog, t, textInput, voiceOnlyMode]);

  useEffect(() => {
    if (!selectedPromptCode) return;
    const selected = prompts.find((item) => item.code === selectedPromptCode);
    if (!selected) return;
    setSystemInstruction(selected.systemPrompt || '');
    setModel((previous) => {
      const promptModel = (selected.llmModel || '').trim();
      if (!promptModel || previous === promptModel) {
        return previous;
      }
      return promptModel;
    });
    const signature = `${selected.code}|${selected.name}`;
    if (lastLoadedPromptLogRef.current === signature) {
      return;
    }
    lastLoadedPromptLogRef.current = signature;
    pushLog(
      'info',
      t('pages:test.voiceLab.direct.logs.promptLoaded', 'Loaded Prompt template: {{name}} ({{code}})', {
        name: selected.name,
        code: selected.code,
      })
    );
  }, [prompts, pushLog, selectedPromptCode, t]);

  useEffect(() => {
    return () => {
      if (hasActiveMicrophoneResources()) {
        stopMicrophone();
      }
      sessionRef.current?.close();
      sessionRef.current = null;
      suppressGeminiTurnRef.current = false;
      resetRemotePlayback();
    };
  }, [hasActiveMicrophoneResources, resetRemotePlayback, stopMicrophone]);

  return {
    socketStatus,
    wsOpen,
    micStatus,
    error,
    setError,
    info,
    setInfo,
    model,
    setModel,
    modalities,
    setModalities,
    voice,
    setVoice,
    systemInstruction,
    setSystemInstruction,
    prompts,
    loadingPrompts,
    selectedPromptCode,
    setSelectedPromptCode,
    textInput,
    setTextInput,
    sessionId,
    assistantText,
    inputTranscript,
    outputTranscript,
    totalTokens,
    logs,
    displayWsUrl,
    testCallId: finalizeResult?.call_id || testSession?.call_id || '',
    finalizeResult,
    canUseRealtimeInput,
    voiceOnlyMode,
    connectSocket,
    disconnectSocket,
    clearConsole,
    sendText,
    toggleMicrophone,
  };
}

export const useLiveWebSocketConsole = useVoiceTestConsole;
