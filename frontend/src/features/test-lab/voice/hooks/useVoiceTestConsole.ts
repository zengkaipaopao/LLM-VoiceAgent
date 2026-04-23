import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
        `Failed to persist voice test transcript: ${persistError instanceof Error ? persistError.message : String(persistError)}`
      );
    });

    appendRequestChainRef.current = appendRequestChainRef.current.then(() => task);
    await appendRequestChainRef.current;
  }, [pushLog]);

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
            ? result.extraction?.message || '语音测试会话已结束，预约提取已完成。'
            : '语音测试会话已结束。'
        );
        return result;
      } catch (finalizeError) {
        const message =
          finalizeError instanceof Error ? finalizeError.message : String(finalizeError);
        setError(message);
        pushLog('error', `Failed to finalize voice test session: ${message}`);
        return null;
      } finally {
        finalizeInFlightRef.current = false;
      }
    },
    [pushLog]
  );

  const handlePromptLoadError = useCallback(
    (loadError: unknown) => {
      pushLog('error', `Failed to load prompts: ${String(loadError)}`);
    },
    [pushLog]
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
        pushLog('success', `AI(业务流): ${finalized}`);
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
          setInfo(`已通过业务状态机完成预约${result.operation === 'cancel' ? '取消' : '变更'}。`);
        } else if (result.operation) {
          setInfo(`已进入预约${result.operation === 'cancel' ? '取消' : '变更'}业务流程。`);
        }
        pushLog(
          'info',
          `ChatService operation flow handled turn: operation=${result.operation || '-'} state=${result.state_status || '-'} executed=${result.executed ? 'yes' : 'no'}`
        );
        return true;
      } catch (operationError) {
        pushLog(
          'error',
          `Failed to advance ChatService operation flow: ${operationError instanceof Error ? operationError.message : String(operationError)}`
        );
        return false;
      }
    },
    [appendBackendAssistantTurn, flushPersistedMessages, pushLog]
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
        pushLog('info', 'Detected closing phrase. Auto-finalizing voice test session.');
        closeDirectTransport('Gemini Live direct session auto-closed after closing phrase.');
        const result = await finalizeActiveTestSession(true);
        if (result) {
          setInfo(
            result.extraction?.message || '检测到结束语，已自动断开语音会话并完成提取。'
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

      closeDirectTransport('Gemini Live direct session closed.');
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
      setError('当前模型不是 Gemini Live / Native Audio 模型。请在 Prompt 中选择语音模型，或在此处显式覆盖。');
      pushLog('error', `Incompatible voice test model: ${normalizedModel || '(empty)'}`);
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
        pushLog('info', `Voice test session created: ${createdSession.call_id}`);

        pushLog('info', 'Requesting Gemini Live ephemeral token...');
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
              pushLog('success', 'Gemini Live direct session connected.');
            },
            onmessage: (message) => {
              const payloads = normalizeLiveServerMessage(message);
              for (const payload of payloads) {
                void handlePayload(payload);
              }
            },
            onerror: (event) => {
              const message = event.message || 'Gemini Live direct connection error.';
              setError(message);
              setSocketStatus('error');
              pushLog('error', message);
            },
            onclose: (event) => {
              const detail =
                event.reason && event.reason.length
                  ? `Gemini Live connection closed (code: ${event.code}, reason: ${event.reason}).`
                  : `Gemini Live connection closed (code: ${event.code}).`;
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
        pushLog('error', `Failed to connect to Gemini Live directly: ${message}`);
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
    voice,
    finalizeActiveTestSession,
    finalizeResult,
  ]);

  const sendText = useCallback(() => {
    if (voiceOnlyMode) {
      pushLog('warning', 'Voice-only mode enabled. Text input is disabled in this tab.');
      return;
    }

    const text = textInput.trim();
    if (!text) return;
    if (!sessionRef.current) {
      setError('Gemini Live is not connected.');
      return;
    }

    const now = Date.now();
    const previous = lastTextSendRef.current;
    if (previous.text === text && now - previous.ts < 1200) {
      pushLog('warning', 'Duplicate text input ignored.');
      return;
    }
    lastTextSendRef.current = { text, ts: now };

    sessionRef.current.sendClientContent({ turns: text, turnComplete: true });
    pushLog('info', `Text input: ${text}`);
    setTextInput('');
  }, [pushLog, textInput, voiceOnlyMode]);

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
    pushLog('info', `Loaded prompt template: ${selected.name} (${selected.code})`);
  }, [prompts, pushLog, selectedPromptCode]);

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
