import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { API_BASE_URL } from '../api/http';
import { PromptTemplate } from '../types/shared';
import { usePromptTemplates } from './usePromptTemplates';
import { appendEventLog, EventLog, LogLevel } from './testTabs/eventLog';
import { handleLiveEventPayload } from './liveConsole/eventHandlers';
import { toWebSocketBase } from './liveConsole/socketUtils';
import { closeSocketResources, connectLiveSocket, disconnectLiveSocket } from './liveConsole/socketLifecycle';
import { useHeartbeat } from './liveConsole/useHeartbeat';
import { useMicrophoneStream } from './liveConsole/useMicrophoneStream';
import { useRemoteAudioPlayback } from './liveConsole/useRemoteAudioPlayback';
import { LiveEventPayload, MicStatus, SocketStatus } from './liveConsole/types';

export type { LiveEventPayload, MicStatus, SocketStatus } from './liveConsole/types';
export type { EventLog, LogLevel } from './testTabs/eventLog';
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
  connectSocket: () => void;
  disconnectSocket: () => void;
  clearConsole: () => void;
  sendText: () => void;
  toggleMicrophone: (enabled: boolean) => void;
}

export function useLiveWebSocketConsole(): UseLiveWebSocketConsoleResult {
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

  const wsRef = useRef<WebSocket | null>(null);

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
    preferredCode: 'general_appointment',
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

  const appendAssistantText = useCallback((value: string) => {
    if (value === '\n') {
      setAssistantText((prev) => (prev.endsWith('\n') ? prev : `${prev}\n`));
      return;
    }
    setAssistantText((prev) => prev + value);
  }, []);

  const handlePayload = useCallback(
    async (payload: LiveEventPayload) => {
      await handleLiveEventPayload({
        event: payload,
        setSocketStatus,
        startHeartbeat,
        pushLog,
        setSessionId,
        appendAssistantText,
        setInputTranscript,
        setOutputTranscript,
        playPcmAudioChunk,
        setTotalTokens,
        setError: (value) => setError(value),
      });
    },
    [appendAssistantText, playPcmAudioChunk, pushLog, startHeartbeat]
  );

  const connectSocket = useCallback(() => {
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
  }, [hasActiveMicrophoneResources, resetRemotePlayback, sendLiveEvent, stopHeartbeat, stopMicrophone]);

  const sendText = useCallback(() => {
    const text = textInput.trim();
    if (!text) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket is not connected.');
      return;
    }
    sendLiveEvent({ type: 'text', text });
    pushLog('info', `Text input: ${text}`);
    setTextInput('');
  }, [pushLog, sendLiveEvent, textInput]);

  const clearConsole = useCallback(() => {
    setAssistantText('');
    setInputTranscript('');
    setOutputTranscript('');
    setLogs([]);
    setTotalTokens(0);
    setError(null);
  }, []);

  useEffect(() => {
    if (!selectedPromptCode) return;
    const selected = prompts.find((item) => item.code === selectedPromptCode);
    if (!selected) return;
    setSystemInstruction(selected.systemPrompt || '');
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
    connectSocket,
    disconnectSocket,
    clearConsole,
    sendText,
    toggleMicrophone,
  };
}
