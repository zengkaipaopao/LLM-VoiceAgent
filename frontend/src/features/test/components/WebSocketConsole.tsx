import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Tile } from '@carbon/react';

import { PromptTemplate } from '../../../types';
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
];

const connectionTagMap: Record<ConnectionState, ConnectionSummary> = {
  idle: { label: '待连接', type: 'cool-gray' },
  connecting: { label: '连接中', type: 'blue' },
  connected: { label: '已连接', type: 'teal' },
  error: { label: '连接异常', type: 'red' },
};

const defaultInstructions =
  '你是 LLM Voice Agent 的实时调试助手，请使用自然、专业的中文语气与用户对话，必要时解释你的推理。';
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
  const { reloadReservations } = useAppState();
  const [input, setInput] = useState('');
  const [autoReply, setAutoReply] = useState(true);
  const historyRef = useRef<HTMLDivElement | null>(null);
  const ttsCapabilityEnabled = prompt?.capabilities?.ttsEnabled ?? true;
  const voiceConfig = prompt?.voiceConfig;
  const appointmentEnabled = prompt?.capabilities?.appointmentLogging ?? false;
  const instructions = useMemo(() => {
    const base = prompt?.systemPrompt ?? defaultInstructions;
    const welcome = prompt?.welcomeMessage?.trim();
    const hints: string[] = [];
    if (welcome) {
      hints.push(`会话建立后请率先播报以下欢迎语：${welcome}`);
    }
    if (voiceConfig?.voice) {
      hints.push(`如需语音输出，请匹配 OpenAI 声音预设：${voiceConfig.voice}。`);
    }
    if (voiceConfig?.speakingRate) {
      hints.push(`请保持语速约为 ${voiceConfig.speakingRate} 倍，兼顾清晰与自然。`);
    }
    if (appointmentEnabled) {
      hints.push('在正式确认预约前，请主动询问一句：“追加依頼などのご要望はございますか？”，以确认是否存在补充需求。');
      hints.push(
        `[预约记录输出规则]
- 仅在收集完整的联系人 / 公司 / 希望日期时间 / 回收类型 / 量 / 地址 / 追加要望后，才可输出 JSON。
- JSON 需使用三个反引号包裹，字段包含：operation（create=新規 / update=変更 / delete=取消）、timestamp（日本时间 ISO8601）、caller_name、company、appointment、category、amount、address、summary。
- JSON 中需包含 extra_request 字段，写入客户追加要望（如无则不要输出 JSON）。
- JSON 输出后，再用自然语言告知用户“已记录完毕”。`,
      );
      hints.push(
        '结束语需固定为：“ご予約内容を受付いたしました。ご利用ありがとうございます。”，且不得添加“少々お待ちください”等等待提示或透露内部处理流程。',
      );
      hints.push('当信息齐全准备输出 JSON 时，直接输出 JSON 与结束语，禁止在对话中说“少々お待ちください”或“记录を行います”等等待提示。');
      hints.push('请勿要求客户输入“受付完了”等指令，信息齐全后由你直接输出 JSON 与结束语。');
    }
    return hints.length ? `${base}\n\n[语音指引]\n${hints.join('\n')}` : base;
  }, [appointmentEnabled, prompt?.systemPrompt, prompt?.welcomeMessage, voiceConfig?.speakingRate]);
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
  const {
    message: appointmentMessage,
    saving: savingAppointment,
    handleAssistantMessage: handleAppointmentMessage,
    createAppointment,
    reset: resetAppointment,
  } = useAppointmentRecorder({
    enabled: appointmentEnabled,
    messages: realtime.messages,
    onCreated: reloadReservations,
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
