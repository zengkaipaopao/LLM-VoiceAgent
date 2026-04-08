import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { API_BASE_URL } from '../../../../api/http';
import { PromptTemplate } from '../../../../types/shared';
import { appendEventLog, EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';
import { handleLiveEventPayload } from '../../../../hooks/liveConsole/eventHandlers';
import { closeSocketResources, connectLiveSocket, disconnectLiveSocket } from '../../../../hooks/liveConsole/socketLifecycle';
import { toWebSocketBase } from '../../../../hooks/liveConsole/socketUtils';
import { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
import { useHeartbeat } from '../../../../hooks/liveConsole/useHeartbeat';
import { useMicrophoneStream } from '../../../../hooks/liveConsole/useMicrophoneStream';
import { useRemoteAudioPlayback } from '../../../../hooks/liveConsole/useRemoteAudioPlayback';
import { usePromptTemplates } from '../../../../hooks/usePromptTemplates';

export type { LiveEventPayload, MicStatus, SocketStatus } from '../../../../hooks/liveConsole/types';
export type { EventLog, LogLevel } from '../../../../hooks/testTabs/eventLog';

const LIVE_API_KEY = (import.meta.env.VITE_APP_API_KEY ?? '').trim();

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

export function useVoiceTestConsole(): UseLiveWebSocketConsoleResult {
  const [socketStatus, setSocketStatus] = useState<SocketStatus>('disconnected');
  const [wsOpen, setWsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [model, setModel] = useState('gemini-3.1-flash-live-preview');
  const [modalities, setModalities] = useState('AUDIO');
  const [voice, setVoice] = useState('');
  const [systemInstruction, setSystemInstruction] = useState(
    'You are a helpful bilingual voice assistant for customer service.'
  );
  const [textInput, setTextInput] = useState('');

  const [sessionId, setSessionId] = useState<string>('');
  const [assistantText, setAssistantText] = useState('');
  const [inputTranscript, setInputTranscript] = useState('');
  const [outputTranscript, setOutputTranscript] = useState('');
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [logs, setLogs] = useState<EventLog[]>([]);
  const voiceOnlyMode = true;

  const wsRef = useRef<WebSocket | null>(null);
  const inputTranscriptHistoryRef = useRef('');
  const inputTranscriptTurnRef = useRef('');
  const outputTranscriptHistoryRef = useRef('');
  const outputTranscriptTurnRef = useRef('');
  const lastLoggedInputRef = useRef('');
  const lastLoggedOutputRef = useRef('');
  const lastLoadedPromptLogRef = useRef('');
  const lastTextSendRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });

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

  const wsUrl = useMemo(() => {
    const base = toWebSocketBase(API_BASE_URL);
    const params = new URLSearchParams();
    if (model.trim()) params.set('model', model.trim());
    if (modalities.trim()) params.set('modalities', modalities.trim());
    if (voice.trim()) params.set('voice', voice.trim());
    if (LIVE_API_KEY) params.set('api_key', LIVE_API_KEY);
    if (selectedPromptCode.trim()) {
      params.set('template_code', selectedPromptCode.trim());
    } else if (systemInstruction.trim()) {
      params.set('system_instruction', systemInstruction.trim());
    }
    return `${base}/live/ws?${params.toString()}`;
  }, [model, modalities, voice, selectedPromptCode, systemInstruction]);

  const displayWsUrl = useMemo(() => wsUrl.replace(/([?&]api_key=)[^&]*/i, '$1***'), [wsUrl]);

  const sendLiveEvent = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }, []);

  const getWebSocket = useCallback(() => wsRef.current, []);

  const sendPing = useCallback(() => {
    sendLiveEvent({ type: 'ping' });
  }, [sendLiveEvent]);

  const { startHeartbeat, stopHeartbeat } = useHeartbeat({ sendPing });

  const { playPcmAudioChunk, resetRemotePlayback } = useRemoteAudioPlayback({ pushLog });

  const {
    micStatus,
    stopMicrophone,
    resetMicrophone,
    toggleMicrophone,
    hasActiveMicrophoneResources,
  } = useMicrophoneStream({
    getWebSocket,
    sendLiveEvent,
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
        startHeartbeat,
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
      startHeartbeat,
    ]
  );

  const connectSocket = useCallback(() => {
    inputTranscriptHistoryRef.current = '';
    inputTranscriptTurnRef.current = '';
    outputTranscriptHistoryRef.current = '';
    outputTranscriptTurnRef.current = '';
    lastLoggedInputRef.current = '';
    lastLoggedOutputRef.current = '';
    lastLoadedPromptLogRef.current = '';
    lastTextSendRef.current = { text: '', ts: 0 };
    connectLiveSocket({
      wsRef,
      wsUrl,
      displayWsUrl,
      pushLog,
      setError: (value) => setError(value),
      setSocketStatus,
      setAssistantText: (value) => setAssistantText(value),
      setInputTranscript,
      setOutputTranscript,
      setTotalTokens,
      setSessionId,
      setWsOpen,
      handlePayload,
      stopHeartbeat,
      hasActiveMicrophoneResources,
      resetRemotePlayback,
      resetMicrophone,
    });
  }, [
    displayWsUrl,
    handlePayload,
    hasActiveMicrophoneResources,
    pushLog,
    resetMicrophone,
    resetRemotePlayback,
    stopHeartbeat,
    wsUrl,
  ]);

  const disconnectSocket = useCallback(() => {
    flushTranscriptTurns();
    disconnectLiveSocket({
      wsRef,
      stopHeartbeat,
      hasActiveMicrophoneResources,
      stopMicrophone,
      sendLiveEvent,
      setSocketStatus,
      setWsOpen,
      setSessionId,
      resetRemotePlayback,
    });
  }, [
    flushTranscriptTurns,
    hasActiveMicrophoneResources,
    resetRemotePlayback,
    sendLiveEvent,
    stopHeartbeat,
    stopMicrophone,
  ]);

  const sendText = useCallback(() => {
    if (voiceOnlyMode) {
      pushLog('warning', 'Voice-only mode enabled. Text input is disabled in this tab.');
      return;
    }

    const text = textInput.trim();
    if (!text) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket is not connected.');
      return;
    }

    const now = Date.now();
    const previous = lastTextSendRef.current;
    if (previous.text === text && now - previous.ts < 1200) {
      pushLog('warning', 'Duplicate text input ignored.');
      return;
    }
    lastTextSendRef.current = { text, ts: now };

    sendLiveEvent({ type: 'text', text });
    pushLog('info', `Text input: ${text}`);
    setTextInput('');
  }, [pushLog, sendLiveEvent, textInput, voiceOnlyMode]);

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

  useEffect(() => {
    if (!selectedPromptCode) return;
    const selected = prompts.find((item) => item.code === selectedPromptCode);
    if (!selected) return;
    setSystemInstruction(selected.systemPrompt || '');
    const signature = `${selected.code}|${selected.name}`;
    if (lastLoadedPromptLogRef.current === signature) {
      return;
    }
    lastLoadedPromptLogRef.current = signature;
    pushLog('info', `Loaded prompt template: ${selected.name} (${selected.code})`);
  }, [prompts, pushLog, selectedPromptCode]);

  useEffect(() => {
    return () => {
      closeSocketResources({
        wsRef,
        stopHeartbeat,
        hasActiveMicrophoneResources,
        stopMicrophone,
        resetRemotePlayback,
      });
    };
  }, [hasActiveMicrophoneResources, resetRemotePlayback, stopHeartbeat, stopMicrophone]);

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
