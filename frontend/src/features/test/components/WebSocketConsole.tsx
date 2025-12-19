import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Tile } from '@carbon/react';

import { PromptTemplate, ReservationRecord } from '../../../types';
import { useAppState } from '../../../state/AppStateContext';
import { AppointmentPanel } from './websocket/AppointmentPanel';
import { ChatHistory } from './websocket/ChatHistory';
import { ChatInputPanel } from './websocket/ChatInputPanel';
import { SessionInfoPanel } from './websocket/SessionInfoPanel';
import { SessionStatusCard } from './websocket/SessionStatusCard';
import { TtsPanel } from './websocket/TtsPanel';
import { ConnectionState, ConnectionSummary, SessionStats } from './websocket/types';
import { useRealtimeSession } from '../hooks/useRealtimeSession';
import { useTtsControls } from '../hooks/useTtsControls';
import { useAppointmentRecorder } from '../hooks/useAppointmentRecorder';
import { sanitizeAssistantContent } from '../utils/assistant';

const quickPrompts = [
  '株式会社EIIのコウです。2025年6月3日午前10時、神田2-4-33で粗大ゴミ4トンの回収をお願いします。追加の要望はありません。',
  'お世話になります。XYZ株式会社のサトウです。2025年7月15日午後2時に渋谷区1-5-10でオフィス家具の回収をお願いしたいです。時間厳守お願いします。',
  'こんにちは、ABC商事のタナカです。2025年8月20日午前9時に新宿区3-12-5で引っ越しゴミの回収をお願いします。車２台で来てください。',
];

const connectionTagMap: Record<ConnectionState, ConnectionSummary> = {
  idle: { label: '待连接', type: 'cool-gray' },
  connecting: { label: '连接中', type: 'blue' },
  connected: { label: '已连接', type: 'teal' },
  error: { label: '连接异常', type: 'red' },
};

const defaultInstructions =
  'You are the LLM Voice Agent realtime assistant. Converse in a calm professional tone, explain your reasoning when necessary, and keep every reply concise.';
const fallbackModel = 'gpt-4o-realtime-preview-2024-12-17';

const formatTime = (timestamp?: string | number) => {
  if (!timestamp) return '--:--';
  const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '--:--';
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

type WebSocketConsoleProps = {
  prompt?: PromptTemplate;
};

export function WebSocketConsole({ prompt }: WebSocketConsoleProps) {
  const { appendReservation, reloadReservations } = useAppState();
  const [input, setInput] = useState('');
  const [autoReply, setAutoReply] = useState(true);
  const historyRef = useRef<HTMLDivElement | null>(null);
  const ttsCapabilityEnabled = prompt?.capabilities?.ttsEnabled ?? true;
  const voiceConfig = prompt?.voiceConfig;
  const appointmentEnabled = prompt?.capabilities?.appointmentLogging ?? false;
  const instructions = useMemo(
    () => prompt?.instructions || prompt?.systemPrompt || defaultInstructions,
    [prompt?.instructions, prompt?.systemPrompt],
  );
  const activeModel = prompt?.modelId || fallbackModel;
  const activeVoice = voiceConfig?.voice;
  const ttsControls = useTtsControls({ capabilityEnabled: ttsCapabilityEnabled, initialVoice: voiceConfig?.voice });
  const appointmentHandlerRef = useRef<((text: string) => void) | null>(null);
  const handleAssistantMessage = useCallback(
    (text: string) => {
      const sanitized = sanitizeAssistantContent(text);
      if (!sanitized) {
        appointmentHandlerRef.current?.(text);
        return;
      }
      void ttsControls.handleAssistantMessage(sanitized);
      appointmentHandlerRef.current?.(text);
    },
    [ttsControls.handleAssistantMessage],
  );
  const realtime = useRealtimeSession({
    instructions,
    model: activeModel,
    voice: activeVoice,
    onAssistantMessage: handleAssistantMessage,
  });
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
    handleAssistantMessage: handleAppointmentMessage,
    createAppointment,
    reset: resetAppointment,
  } = useAppointmentRecorder({
    enabled: appointmentEnabled,
    messages: realtime.messages,
    onCreated: handleReservationCreated,
    onAutoCreate: () => {
      realtime.disconnect();
    },
  });

  useEffect(() => {
    appointmentHandlerRef.current = handleAppointmentMessage;
  }, [handleAppointmentMessage]);

  const handleConnect = useCallback(() => {
    void realtime.connect();
  }, [realtime]);

  const handleDisconnect = useCallback(() => {
    resetAppointment();
    realtime.disconnect();
  }, [resetAppointment, realtime]);

  const handleClearConversation = useCallback(() => {
    resetAppointment();
    realtime.clearConversation();
  }, [resetAppointment, realtime]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || realtime.isAssistantTyping || realtime.connectionState !== 'connected') return;
    realtime.recordUserMessage(trimmed);
    setInput('');
    const sent = realtime.sendUserMessage(trimmed);
    if (sent && autoReply) {
      realtime.requestAssistantReply();
    }
  };

  useEffect(() => {
    const container = historyRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [realtime.messages]);

  useEffect(() => {
    resetAppointment();
  }, [resetAppointment, prompt?.id]);

  useEffect(() => {
    if (realtime.connectionState === 'idle' && realtime.messages.length === 0) {
      resetAppointment();
    }
  }, [realtime.connectionState, realtime.messages.length, resetAppointment]);

  const stats = useMemo<SessionStats>(() => {
    const userTurns = realtime.messages.filter((message) => message.role === 'user').length;
    const assistantTurns = realtime.messages.filter((message) => message.role === 'assistant').length;
    return {
      totalTurns: realtime.messages.length,
      userTurns,
      assistantTurns,
      lastUpdated: realtime.messages[realtime.messages.length - 1]?.timestamp,
    };
  }, [realtime.messages]);

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
  };

  const toggleAutoReply = () => {
    setAutoReply((prev) => !prev);
  };

  const connectionSummary = connectionTagMap[realtime.connectionState];
  const displayModel = realtime.sessionMeta?.model ?? activeModel;
  const appointmentButtonDisabled =
    !realtime.messages.length || savingAppointment || realtime.connectionState === 'connecting';

  return (
    <div className="ws-console">
      <div className="ws-console__main">
        <SessionStatusCard
          connectionSummary={connectionSummary}
          promptName={prompt?.name}
          displayModel={displayModel}
          sessionMeta={realtime.sessionMeta}
          connectionState={realtime.connectionState}
          sessionError={realtime.sessionError}
          messageCount={realtime.messages.length}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
          onClear={handleClearConversation}
        />
        <div className="ws-console__grid">
          <Tile className="ws-chat-panel">
            <ChatHistory
              messages={realtime.messages}
              historyRef={historyRef}
              formatTime={formatTime}
              isAssistantTyping={realtime.isAssistantTyping}
            />
          </Tile>
          <ChatInputPanel
            input={input}
            onInputChange={setInput}
            onSubmit={handleSubmit}
            connectionState={realtime.connectionState}
            isAssistantTyping={realtime.isAssistantTyping}
            autoReply={autoReply}
            onManualReply={realtime.requestAssistantReply}
            quickPrompts={quickPrompts}
            onQuickPromptSelect={handleQuickPrompt}
          />
        </div>
      </div>
      <div className="ws-console__side">
        <SessionInfoPanel
          sessionMeta={realtime.sessionMeta}
          connectionSummary={connectionSummary}
          stats={stats}
          formatTime={formatTime}
          autoReply={autoReply}
          onToggleAutoReply={toggleAutoReply}
        />
        {ttsCapabilityEnabled && (
          <TtsPanel
            capabilityEnabled={ttsCapabilityEnabled}
            providerOptions={ttsControls.providerOptions}
            provider={ttsControls.provider}
            onProviderChange={ttsControls.setProvider}
            language={ttsControls.language}
            onLanguageChange={ttsControls.setLanguage}
            googleLanguages={ttsControls.languageOptions}
            enabled={ttsControls.enabled}
            onToggleEnabled={() => ttsControls.setEnabled(!ttsControls.enabled)}
            model={ttsControls.model}
            onModelChange={ttsControls.setModel}
            modelOptions={ttsControls.modelOptions}
            voice={ttsControls.voice}
            onVoiceChange={ttsControls.setVoice}
            voiceOptions={ttsControls.voiceOptions}
            speakingRate={ttsControls.speakingRate}
            onSpeakingRateChange={ttsControls.setSpeakingRate}
            pitch={ttsControls.pitch}
            onPitchChange={ttsControls.setPitch}
            status={ttsControls.status}
            controlsDisabled={ttsControls.controlsDisabled}
            audioRef={ttsControls.audioRef}
          />
        )}
        <AppointmentPanel
          enabled={appointmentEnabled}
          message={appointmentMessage}
          onCreate={() => {
            void createAppointment();
          }}
          disabled={appointmentButtonDisabled}
          saving={savingAppointment}
        />
      </div>
    </div>
  );
}
