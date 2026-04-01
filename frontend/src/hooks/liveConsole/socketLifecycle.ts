import { LogLevel } from '../testTabs/eventLog';
import { LiveEventPayload, SocketStatus } from './types';

interface CloseSocketResourcesOptions {
  wsRef: { current: WebSocket | null };
  stopHeartbeat: () => void;
  hasActiveMicrophoneResources: () => boolean;
  stopMicrophone: () => void;
  resetRemotePlayback: () => void;
}

interface ConnectLiveSocketOptions {
  wsRef: { current: WebSocket | null };
  wsUrl: string;
  displayWsUrl: string;
  pushLog: (level: LogLevel, message: string) => void;
  setError: (value: string | null) => void;
  setSocketStatus: (value: SocketStatus) => void;
  setAssistantText: (value: string) => void;
  setInputTranscript: (value: string) => void;
  setOutputTranscript: (value: string) => void;
  setTotalTokens: (value: number) => void;
  setSessionId: (value: string) => void;
  setWsOpen: (value: boolean) => void;
  handlePayload: (payload: LiveEventPayload) => Promise<void>;
  stopHeartbeat: () => void;
  hasActiveMicrophoneResources: () => boolean;
  resetRemotePlayback: () => void;
  resetMicrophone: () => void;
}

interface DisconnectLiveSocketOptions extends CloseSocketResourcesOptions {
  sendLiveEvent: (payload: Record<string, unknown>) => void;
  setSocketStatus: (value: SocketStatus) => void;
  setWsOpen: (value: boolean) => void;
  setSessionId: (value: string) => void;
}

export function closeSocketResources({
  wsRef,
  stopHeartbeat,
  hasActiveMicrophoneResources,
  stopMicrophone,
  resetRemotePlayback,
}: CloseSocketResourcesOptions): void {
  stopHeartbeat();
  if (hasActiveMicrophoneResources()) {
    stopMicrophone();
  }
  wsRef.current?.close();
  wsRef.current = null;
  resetRemotePlayback();
}

export function connectLiveSocket({
  wsRef,
  wsUrl,
  displayWsUrl,
  pushLog,
  setError,
  setSocketStatus,
  setAssistantText,
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
}: ConnectLiveSocketOptions): void {
  if (wsRef.current) {
    const { readyState } = wsRef.current;
    if (readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) {
      return;
    }
  }

  stopHeartbeat();
  setError(null);
  setSocketStatus('connecting');
  setAssistantText('');
  setInputTranscript('');
  setOutputTranscript('');
  setTotalTokens(0);
  setSessionId('');
  setWsOpen(false);
  pushLog('info', `Connecting to ${displayWsUrl}`);

  const ws = new WebSocket(wsUrl);
  wsRef.current = ws;

  ws.onopen = () => {
    if (wsRef.current !== ws) {
      ws.close();
      return;
    }
    setWsOpen(true);
    setSocketStatus('connecting');
    pushLog('success', 'WebSocket connected. Waiting for Gemini Live session...');
  };

  ws.onmessage = (event) => {
    if (wsRef.current !== ws) {
      return;
    }

    try {
      const payload = JSON.parse(event.data) as LiveEventPayload;
      void handlePayload(payload);
    } catch (parseError) {
      pushLog('warning', `Failed to parse message: ${String(parseError)}`);
    }
  };

  ws.onerror = () => {
    if (wsRef.current !== ws) {
      return;
    }
    setSocketStatus('error');
    setError('WebSocket connection error.');
    pushLog('error', 'WebSocket connection error.');
  };

  ws.onclose = (event) => {
    if (wsRef.current !== ws) {
      return;
    }

    stopHeartbeat();
    setSocketStatus('disconnected');
    setWsOpen(false);

    const closeDetail = event.reason
      ? `WebSocket disconnected (code: ${event.code}, reason: ${event.reason}).`
      : `WebSocket disconnected (code: ${event.code}).`;
    pushLog('info', closeDetail);

    wsRef.current = null;
    if (hasActiveMicrophoneResources()) {
      resetMicrophone();
    }
    setSessionId('');
    resetRemotePlayback();
  };
}

export function disconnectLiveSocket({
  wsRef,
  stopHeartbeat,
  hasActiveMicrophoneResources,
  stopMicrophone,
  sendLiveEvent,
  setSocketStatus,
  setWsOpen,
  setSessionId,
  resetRemotePlayback,
}: DisconnectLiveSocketOptions): void {
  stopHeartbeat();
  if (hasActiveMicrophoneResources()) {
    stopMicrophone();
  }
  sendLiveEvent({ type: 'close' });
  wsRef.current?.close();
  wsRef.current = null;
  setSocketStatus('disconnected');
  setWsOpen(false);
  setSessionId('');
  resetRemotePlayback();
}
