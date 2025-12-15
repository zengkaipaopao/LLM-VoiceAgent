import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { createRealtimeSession } from '../../../api/realtime';
import { PromptTemplate, ReservationRecord } from '../../../types';
import { useAppState } from '../../../state/AppStateContext';
import { useAppointmentRecorder } from '../hooks/useAppointmentRecorder';
import { sanitizeAssistantContent } from '../utils/assistant';
import { getTextDelta } from '../utils/realtime';
import { AppointmentPanel } from './websocket/AppointmentPanel';
import { ChatMessage } from './websocket/types';
import { RtcControlsPanel } from './webrtc/RtcControlsPanel';
import { RtcLogsPanel } from './webrtc/RtcLogsPanel';
import { RtcStatusCard } from './webrtc/RtcStatusCard';
import { ConsoleLog, RtcState, RtcStateTag } from './webrtc/types';

const defaultInstructions =
  'Use WebRTC to maintain bidirectional audio and data control, narrate your reasoning in real time, and keep the experience professional.';
const fallbackModel = 'gpt-4o-realtime-preview-2024-12-17';

const formatTime = (timestamp: string) =>
  new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

type WebRtcConsoleProps = {
  prompt?: PromptTemplate;
};

export function WebRtcConsole({ prompt }: WebRtcConsoleProps) {
  const { appendReservation, reloadReservations } = useAppState();
  const [rtcState, setRtcState] = useState<RtcState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionMeta, setSessionMeta] = useState<{ id: string; model: string } | null>(null);
  const [command, setCommand] = useState('');
  const [logs, setLogs] = useState<ConsoleLog[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const appointmentHandlerRef = useRef<((text: string) => void) | null>(null);
  const autoCleanupRef = useRef<() => void>(() => {});
  const responseBufferRef = useRef<Record<string, string>>({});
  const pendingResponseRef = useRef<string | null>(null);

  const voiceConfig = prompt?.voiceConfig;
  const appointmentEnabled = prompt?.capabilities?.appointmentLogging ?? false;
  const instructions = useMemo(
    () => prompt?.instructions || prompt?.systemPrompt || defaultInstructions,
    [prompt?.instructions, prompt?.systemPrompt],
  );
  const activeModel = prompt?.modelId ?? fallbackModel;
  const activeVoice = voiceConfig?.voice;
  const noiseSuppressionEnabled = voiceConfig?.noiseSuppression ?? true;

  const appendLog = useCallback((entry: Omit<ConsoleLog, 'id' | 'timestamp'>) => {
    setLogs((prev) => [
      ...prev,
      {
        ...entry,
        id: `${entry.direction}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        timestamp: new Date().toISOString(),
      },
    ]);
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const recordAssistantMessage = useCallback((content: string) => {
    const timestamp = new Date().toISOString();
    setMessages((prev) => [...prev, { id: `assistant-${timestamp}`, role: 'assistant', content, timestamp }]);
  }, []);

  const recordUserMessage = useCallback((content: string) => {
    const timestamp = new Date().toISOString();
    setMessages((prev) => [...prev, { id: `user-${timestamp}`, role: 'user', content, timestamp }]);
  }, []);

  const handleReservationCreated = useCallback(
    async (record: ReservationRecord) => {
      try {
        appendReservation(record);
      } catch (error) {
        console.warn('追加预约记录失败，改为重新加载', error);
        await reloadReservations();
      }
    },
    [appendReservation, reloadReservations],
  );

  const {
    message: appointmentMessage,
    saving: savingAppointment,
    handleAssistantMessage,
    createAppointment,
    reset: resetAppointment,
  } = useAppointmentRecorder({
    enabled: appointmentEnabled,
    messages,
    autoFinalizeOnSummary: true,
    onCreated: handleReservationCreated,
    onAutoCreate: () => autoCleanupRef.current(),
  });

  useEffect(() => {
    appointmentHandlerRef.current = handleAssistantMessage;
  }, [handleAssistantMessage]);

  const cleanupConnection = useCallback(() => {
    dataChannelRef.current?.close();
    dataChannelRef.current = null;
    peerRef.current?.close();
    peerRef.current = null;
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
    responseBufferRef.current = {};
    pendingResponseRef.current = null;
    setRtcState('idle');
    setMessages([]);
    resetAppointment();
  }, [resetAppointment]);

  useEffect(() => {
    autoCleanupRef.current = () => {
      cleanupConnection();
      appendLog({ direction: 'system', message: '通话结束，已断开 WebRTC 连接' });
    };
  }, [appendLog, cleanupConnection]);

  useEffect(() => {
    setMessages([]);
    clearLogs();
    resetAppointment();
  }, [prompt?.id, clearLogs, resetAppointment]);

  useEffect(() => () => cleanupConnection(), [cleanupConnection]);

  const handleFinalAssistantText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      recordAssistantMessage(text);
      appointmentHandlerRef.current?.(text);
      const sanitized = sanitizeAssistantContent(text);
      if (sanitized.trim()) {
        appendLog({ direction: 'in', message: sanitized });
      }
    },
    [appendLog, recordAssistantMessage],
  );

  const processRealtimeFrame = useCallback(
    (payload: string) => {
      try {
        const frame = JSON.parse(payload);
        switch (frame.type) {
          case 'response.created': {
            const responseId = frame.response?.id as string | undefined;
            if (responseId) {
              responseBufferRef.current[responseId] = '';
              pendingResponseRef.current = responseId;
            }
            break;
          }
          case 'response.output_text.delta':
          case 'response.text.delta': {
            const responseId = (frame.response_id as string | undefined) ?? pendingResponseRef.current;
            const delta = getTextDelta(frame);
            if (responseId && delta) {
              responseBufferRef.current[responseId] = (responseBufferRef.current[responseId] ?? '') + delta;
            }
            break;
          }
          case 'response.output_text.done':
          case 'response.text.done':
          case 'response.completed':
          case 'response.done': {
            const responseId =
              (frame.response?.id as string | undefined) ??
              (frame.response_id as string | undefined) ??
              pendingResponseRef.current;
            if (responseId) {
              const finalText = responseBufferRef.current[responseId];
              delete responseBufferRef.current[responseId];
              pendingResponseRef.current = null;
              if (finalText) {
                handleFinalAssistantText(finalText);
              }
            }
            break;
          }
          default:
            break;
        }
      } catch {
        const extracted = extractRealtimeText(payload) ?? payload;
        handleFinalAssistantText(extracted);
      }
    },
    [handleFinalAssistantText],
  );

  const setupRemoteAudio = useCallback((pc: RTCPeerConnection) => {
    const remoteStream = new MediaStream();
    pc.ontrack = (event) => {
      event.streams[0].getTracks().forEach((track) => remoteStream.addTrack(track));
      const audio = remoteAudioRef.current;
      if (audio) {
        audio.srcObject = remoteStream;
        audio.play().catch((err) => console.warn('自动播放受限', err));
      }
    };
  }, []);

  const configureDataChannel = useCallback(
    (pc: RTCPeerConnection) => {
      const channel = pc.createDataChannel('oai-events');
      dataChannelRef.current = channel;
      channel.onopen = () => {
        appendLog({ direction: 'system', message: 'DataChannel 已建立' });
        const payload = JSON.stringify({ type: 'response.create' });
        channel.send(payload);
        appendLog({ direction: 'out', message: payload });
      };
      channel.onerror = (event) => appendLog({ direction: 'system', message: `DataChannel 错误: ${event}` });
      channel.onmessage = (event) => {
        if (typeof event.data === 'string') {
          processRealtimeFrame(event.data);
        } else {
          appendLog({ direction: 'in', message: '[binary message]' });
        }
      };
    },
    [appendLog, processRealtimeFrame],
  );

  const connectRtc = useCallback(async () => {
    if (rtcState === 'connecting' || rtcState === 'connected') return;
    setRtcState('connecting');
    setError(null);
    try {
      const session = await createRealtimeSession({
        instructions,
        model: activeModel,
        voice: activeVoice,
        channel: 'webrtc',
      });
      const peer = new RTCPeerConnection(session.rtc_configuration ?? undefined);
      peerRef.current = peer;
      setSessionMeta({ id: session.session_id, model: session.model });
      setupRemoteAudio(peer);
      configureDataChannel(peer);

      const audioConstraints: MediaTrackConstraints = {
        noiseSuppression: noiseSuppressionEnabled,
        echoCancellation: true,
        autoGainControl: true,
      };
      const localStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      localStreamRef.current = localStream;
      localStream.getTracks().forEach((track) => peer.addTrack(track, localStream));

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);

      const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=${encodeURIComponent(activeModel)}`, {
        method: 'POST',
        body: offer.sdp ?? '',
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          'Content-Type': 'application/sdp',
        },
      });

      if (!sdpResponse.ok) {
        throw new Error(`OpenAI 返回错误：${await sdpResponse.text()}`);
      }
      const answer = await sdpResponse.text();
      await peer.setRemoteDescription({ type: 'answer', sdp: answer });
      setRtcState('connected');
      appendLog({ direction: 'system', message: 'WebRTC 连接已建立' });
    } catch (err) {
      console.error('建立 WebRTC 连接失败', err);
      setError(err instanceof Error ? err.message : '连接失败');
      cleanupConnection();
      setRtcState('error');
    }
  }, [
    activeModel,
    activeVoice,
    appendLog,
    cleanupConnection,
    configureDataChannel,
    instructions,
    noiseSuppressionEnabled,
    rtcState,
    setupRemoteAudio,
  ]);

  const disconnectRtc = useCallback(() => {
    cleanupConnection();
    appendLog({ direction: 'system', message: '已断开 WebRTC 连接' });
  }, [appendLog, cleanupConnection]);

  const sendCommand = useCallback(() => {
    const text = command.trim();
    if (!text || !dataChannelRef.current || dataChannelRef.current.readyState !== 'open') return;
    const payload = JSON.stringify({ type: 'input_text', text });
    dataChannelRef.current.send(payload);
    appendLog({ direction: 'out', message: payload });
    recordUserMessage(text);
    setCommand('');
  }, [appendLog, command, recordUserMessage]);

  const stateTagMap: Record<RtcState, RtcStateTag> = {
    idle: { label: '待准备', type: 'cool-gray' },
    connecting: { label: '连接中', type: 'blue' },
    connected: { label: '已连接', type: 'teal' },
    error: { label: '异常', type: 'red' },
  };

  return (
    <div className="ws-console">
      <div className="ws-console__main">
        <RtcStatusCard
          stateTag={stateTagMap[rtcState]}
          promptName={prompt?.name}
          modelName={activeModel}
          sessionId={sessionMeta?.id}
          rtcState={rtcState}
          error={error}
          logCount={logs.length}
          onConnect={connectRtc}
          onDisconnect={disconnectRtc}
          onClearLogs={clearLogs}
        />
        <div className="ws-console__grid">
          <RtcControlsPanel
            audioRef={remoteAudioRef}
            command={command}
            onCommandChange={setCommand}
            onSendCommand={sendCommand}
            commandDisabled={rtcState !== 'connected'}
            error={error}
          />
          <RtcLogsPanel logs={logs} formatTime={formatTime} sessionMeta={sessionMeta} />
        </div>
      </div>
      <div className="ws-console__side">
        <AppointmentPanel
          enabled={appointmentEnabled}
          message={appointmentMessage}
          onCreate={() => {
            void createAppointment();
          }}
          disabled={savingAppointment}
          saving={savingAppointment}
        />
      </div>
    </div>
  );
}

function extractRealtimeText(payload: string): string | null {
  try {
    const data = JSON.parse(payload);
    if (typeof data.delta === 'string') return data.delta;
    if (data.delta && typeof data.delta === 'object') {
      if (typeof data.delta.text === 'string') return data.delta.text;
      if (Array.isArray(data.delta.content)) {
        return data.delta.content
          .map((item: unknown) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object' && 'text' in item && typeof (item as { text?: string }).text === 'string') {
              return (item as { text: string }).text;
            }
            return '';
          })
          .join('');
      }
    }
    if (typeof data.text === 'string') return data.text;
  } catch {
    return payload;
  }
  return null;
}
