import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  GoogleGenAI,
  Modality,
  type LiveConnectConfig,
  type LiveServerMessage,
  type Session,
} from '@google/genai';

import { fetchLiveAuthToken } from '../../../../api/live';
import { DEFAULT_LIVE_MODEL, isLiveModelId } from '../../../../config/llmModels';
import { PromptTemplate } from '../../../../types/shared';
import { appendEventLog, EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';
import { handleLiveEventPayload } from '../../../../hooks/liveConsole/eventHandlers';
import { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
import { useMicrophoneStream } from '../../../../hooks/liveConsole/useMicrophoneStream';
import { useRemoteAudioPlayback } from '../../../../hooks/liveConsole/useRemoteAudioPlayback';
import { usePromptTemplates } from '../../../../hooks/usePromptTemplates';

export type { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
export type { EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';

const DEFAULT_DISPLAY_ENDPOINT = 'Gemini Live client-to-server (ephemeral token)';

export interface UseLiveWebSocketConsoleResult {
  socketStatus: SocketStatus;
  wsOpen: boolean;
  micStatus: MicStatus;
  error: string | null;
  setError: (value: string | null) => void;
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
  const voiceOnlyMode = true;

  const sessionRef = useRef<Session | null>(null);
  const inputTranscriptHistoryRef = useRef('');
  const inputTranscriptTurnRef = useRef('');
  const outputTranscriptHistoryRef = useRef('');
  const outputTranscriptTurnRef = useRef('');
  const lastLoggedInputRef = useRef('');
  const lastLoggedOutputRef = useRef('');
  const lastLoadedPromptLogRef = useRef('');
  const lastTextSendRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });
  const isManualDisconnectRef = useRef(false);

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((prev) => appendEventLog(prev, level, message, 180));
  }, []);

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

  const appendInputTranscript = useCallback(
    (chunk: string, isFinal: boolean) => {
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
    },
    [pushLog]
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
    },
    [pushLog]
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
    }
  }, [pushLog]);

  const handlePayload = useCallback(
    async (payload: LiveEventPayload) => {
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
    },
    [
      appendAssistantText,
      appendInputTranscript,
      appendOutputTranscript,
      flushTranscriptTurns,
      playPcmAudioChunk,
      pushLog,
    ]
  );

  const clearConsole = useCallback(() => {
    setAssistantText('');
    setInputTranscript('');
    setOutputTranscript('');
    inputTranscriptHistoryRef.current = '';
    inputTranscriptTurnRef.current = '';
    outputTranscriptHistoryRef.current = '';
    outputTranscriptTurnRef.current = '';
    lastLoggedInputRef.current = '';
    lastLoggedOutputRef.current = '';
    lastLoadedPromptLogRef.current = '';
    lastTextSendRef.current = { text: '', ts: 0 };
    setLogs([]);
    setTotalTokens(0);
    setError(null);
  }, []);

  const disconnectSocket = useCallback(() => {
    isManualDisconnectRef.current = true;
    flushTranscriptTurns();
    if (hasActiveMicrophoneResources()) {
      stopMicrophone();
    }
    sessionRef.current?.close();
    sessionRef.current = null;
    setSocketStatus('disconnected');
    setWsOpen(false);
    setSessionId('');
    resetRemotePlayback();
    pushLog('info', 'Gemini Live direct session closed.');
  }, [flushTranscriptTurns, hasActiveMicrophoneResources, pushLog, resetRemotePlayback, stopMicrophone]);

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
        if (sessionRef.current) {
          sessionRef.current.close();
          sessionRef.current = null;
        }
        if (hasActiveMicrophoneResources()) {
          resetMicrophone();
        }
        resetRemotePlayback();

        setError(null);
        setSocketStatus('connecting');
        setWsOpen(false);
        setAssistantText('');
        setInputTranscript('');
        setOutputTranscript('');
        setTotalTokens(0);
        setSessionId('');
        setDisplayWsUrl(DEFAULT_DISPLAY_ENDPOINT);
        inputTranscriptHistoryRef.current = '';
        inputTranscriptTurnRef.current = '';
        outputTranscriptHistoryRef.current = '';
        outputTranscriptTurnRef.current = '';
        lastLoggedInputRef.current = '';
        lastLoggedOutputRef.current = '';
        lastTextSendRef.current = { text: '', ts: 0 };

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
      resetRemotePlayback();
    };
  }, [hasActiveMicrophoneResources, resetRemotePlayback, stopMicrophone]);

  return {
    socketStatus,
    wsOpen,
    micStatus,
    error,
    setError,
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
