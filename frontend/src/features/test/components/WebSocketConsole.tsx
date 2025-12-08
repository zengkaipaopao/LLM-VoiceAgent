import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, InlineLoading, NumberInput, Select, SelectItem, Tag, TextArea, Tile, Toggle } from '@carbon/react';
import { createRealtimeSession } from '../../../api/realtime';
import { synthesizeSpeech } from '../../../api/tts';
import { createAppointmentFromConversation } from '../../../api/appointments';
import { PromptTemplate } from '../../../types';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  streaming?: boolean;
};

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'error';

const quickPrompts = [
  '请总结刚才的通话亮点',
  '换一个更自然的寒暄开场',
  '继续追问客户的预算范围',
  '模拟客户反对「需要考虑」的处理',
];

const ttsProviderOptions = [
  { id: 'openai', label: 'OpenAI gpt-4o-mini-tts' },
  { id: 'google', label: 'Google Cloud Text-to-Speech' },
] as const;

const ttsModelOptions: Record<
  (typeof ttsProviderOptions)[number]['id'],
  Array<{ id: string; label: string }>
> = {
  openai: [{ id: 'gpt-4o-mini-tts', label: 'gpt-4o-mini-tts' }],
  google: [
    { id: 'google-wavenet', label: 'Wavenet（标准）' },
    { id: 'google-neural2', label: 'Neural2（自然）' },
    { id: 'google-studio', label: 'Studio（高保真）' },
  ],
};

const openAiVoiceOptions = [
  { id: 'alloy', label: 'alloy' },
  { id: 'ballad', label: 'ballad' },
  { id: 'verse', label: 'verse' },
  { id: 'sage', label: 'sage' },
  { id: 'marin', label: 'marin' },
  { id: 'coral', label: 'coral' },
  { id: 'echo', label: 'echo' },
  { id: 'ash', label: 'ash' },
  { id: 'shimmer', label: 'shimmer' },
] as const;

type GoogleVoiceOption = { id: string; label: string };
type GoogleLanguageOption = { code: string; label: string; voices: GoogleVoiceOption[] };

const googleLanguageOptions: GoogleLanguageOption[] = [
  {
    code: 'ja-JP',
    label: '日语',
    voices: [
      { id: 'ja-JP-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'ja-JP-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'ja-JP-Wavenet-C', label: 'Wavenet C · 女声' },
      { id: 'ja-JP-Wavenet-D', label: 'Wavenet D · 男声' },
      { id: 'ja-JP-Neural2-C', label: 'Neural2 C · 女声' },
      { id: 'ja-JP-Neural2-D', label: 'Neural2 D · 男声' },
      { id: 'ja-JP-Studio-Q', label: 'Studio Q · 女声' },
    ],
  },
  {
    code: 'en-US',
    label: '英语（美国）',
    voices: [
      { id: 'en-US-Wavenet-D', label: 'Wavenet D · 男声' },
      { id: 'en-US-Wavenet-F', label: 'Wavenet F · 女声' },
      { id: 'en-US-Neural2-H', label: 'Neural2 H · 女声' },
      { id: 'en-US-Neural2-I', label: 'Neural2 I · 男声' },
      { id: 'en-US-Studio-O', label: 'Studio O · 女声' },
    ],
  },
  {
    code: 'zh-CN',
    label: '中文（普通话）',
    voices: [
      { id: 'cmn-CN-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'cmn-CN-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'cmn-CN-Wavenet-C', label: 'Wavenet C · 女声' },
      { id: 'cmn-CN-Neural2-D', label: 'Neural2 D · 女声' },
    ],
  },
  {
    code: 'ko-KR',
    label: '韩语',
    voices: [
      { id: 'ko-KR-Wavenet-A', label: 'Wavenet A · 女声' },
      { id: 'ko-KR-Wavenet-B', label: 'Wavenet B · 男声' },
      { id: 'ko-KR-Neural2-C', label: 'Neural2 C · 女声' },
    ],
  },
];

const getGoogleVoices = (languageCode: string): GoogleVoiceOption[] => {
  return googleLanguageOptions.find((language) => language.code === languageCode)?.voices ?? [];
};

const connectionTagMap: Record<ConnectionState, { label: string; type: string }> = {
  idle: { label: '待连接', type: 'cool-gray' },
  connecting: { label: '连接中', type: 'blue' },
  connected: { label: '已连接', type: 'teal' },
  error: { label: '连接异常', type: 'red' },
};

const defaultInstructions =
  '你是 LLM Voice Agent 的实时调试助手，请使用自然、专业的中文语气与用户对话，必要时解释你的推理。';
const fallbackModel = 'gpt-4o-realtime-preview-2024-12-17';

const getTextDelta = (payload: unknown): string => {
  if (!payload || typeof payload !== 'object') {
    return '';
  }
  const candidate = payload as Record<string, unknown>;
  if (typeof candidate.delta === 'string') {
    return candidate.delta;
  }
  if (candidate.delta && typeof candidate.delta === 'object') {
    const deltaRecord = candidate.delta as Record<string, unknown>;
    if (typeof deltaRecord.text === 'string') {
      return deltaRecord.text;
    }
    if (Array.isArray(deltaRecord.content)) {
      return deltaRecord.content
        .map((item) => (typeof item === 'string' ? item : (item as Record<string, unknown>).text ?? ''))
        .join('');
    }
  }
  if (typeof candidate.text === 'string') {
    return candidate.text;
  }
  if (Array.isArray(candidate.delta)) {
    return candidate.delta.filter((chunk) => typeof chunk === 'string').join('');
  }
  if (Array.isArray(candidate.content)) {
    return candidate.content
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'text' in item && typeof item.text === 'string') {
          return item.text;
        }
        return '';
      })
      .join('');
  }
  return '';
};

const formatTime = (timestamp?: string | number) => {
  if (!timestamp) return '--:--';
  const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '--:--';
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

const base64ToBlob = (base64: string, contentType: string) => {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i += 1) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: contentType });
};

type WebSocketConsoleProps = {
  prompt?: PromptTemplate;
};

const AUTO_APPOINTMENT_PHRASES = ['ご利用ありがとうございました', 'ご用命ありがとうございました'];

const containsClosingPhrase = (text: string) =>
  AUTO_APPOINTMENT_PHRASES.some((phrase) => text.includes(phrase));

export function WebSocketConsole({ prompt }: WebSocketConsoleProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [autoReply, setAutoReply] = useState(true);
  const [isAssistantTyping, setAssistantTyping] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('idle');
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionMeta, setSessionMeta] = useState<{ id: string; model: string; expires_at?: number } | null>(null);
  const historyRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const responseMessageMapRef = useRef<Record<string, string>>({});
  const responseContentRef = useRef<Record<string, string>>({});
  const pendingResponseRef = useRef<string | null>(null);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [ttsProvider, setTtsProvider] = useState<(typeof ttsProviderOptions)[number]['id']>('openai');
  const [ttsModel, setTtsModel] = useState<string>(ttsModelOptions.openai[0].id);
  const [ttsLanguage, setTtsLanguage] = useState<string>(googleLanguageOptions[0].code);
  const [ttsVoice, setTtsVoice] = useState<string>(openAiVoiceOptions[0].id);
  const [ttsSpeakingRate, setTtsSpeakingRate] = useState<number>(1);
  const [ttsPitch, setTtsPitch] = useState<number>(0);
  const [ttsStatus, setTtsStatus] = useState<string | null>(null);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null);
  const [savingAppointment, setSavingAppointment] = useState(false);
  const [appointmentMessage, setAppointmentMessage] = useState<string | null>(null);
  const manualCloseRef = useRef(false);
  const autoAppointmentTriggeredRef = useRef(false);
  const voiceConfig = prompt?.voiceConfig;
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
    return hints.length ? `${base}\n\n[语音指引]\n${hints.join('\n')}` : base;
  }, [prompt?.systemPrompt, prompt?.welcomeMessage, voiceConfig?.speakingRate]);
  const activeModel = prompt?.modelId || fallbackModel;
  const activeVoice = voiceConfig?.voice;
  const currentTtsVoiceMeta = useMemo(() => {
    if (ttsProvider === 'google') {
      return getGoogleVoices(ttsLanguage).find((voice) => voice.id === ttsVoice);
    }
    return openAiVoiceOptions.find((voice) => voice.id === ttsVoice);
  }, [ttsLanguage, ttsProvider, ttsVoice]);
  const appointmentEnabled = prompt?.capabilities?.appointmentLogging ?? false;

  const speakText = useCallback(
    async (text: string) => {
      if (!ttsEnabled || !text.trim()) return;
      setTtsStatus('正在生成语音...');
      try {
        const result = await synthesizeSpeech({
          text,
          model: ttsModel,
          voice: ttsVoice,
          provider: ttsProvider,
          languageCode: ttsProvider === 'google' ? ttsLanguage : undefined,
          speakingRate: ttsProvider === 'google' ? ttsSpeakingRate : undefined,
          pitch: ttsProvider === 'google' ? ttsPitch : undefined,
        });
        if (ttsAudioUrl) {
          URL.revokeObjectURL(ttsAudioUrl);
        }
        const blob = base64ToBlob(result.audioBase64, result.contentType);
        const url = URL.createObjectURL(blob);
        setTtsAudioUrl(url);
        setTtsStatus('语音已生成，尝试播放...');
        const audio = ttsAudioRef.current;
        if (audio) {
          audio.src = url;
          const playPromise = audio.play();
          if (playPromise) {
            playPromise.catch((err) => {
              console.warn('自动播放受阻', err);
              setTtsStatus('语音生成成功，请手动播放音频。');
            });
          }
        }
      } catch (error) {
        console.error('TTS 合成失败', error);
        setTtsStatus('语音生成失败，请稍后再试。');
      }
    },
    [
      currentTtsVoiceMeta?.languageCode,
      ttsAudioUrl,
      ttsEnabled,
      ttsModel,
      ttsPitch,
      ttsProvider,
      ttsSpeakingRate,
      ttsVoice,
    ],
  );

  const handleCreateAppointment = useCallback(async () => {
    if (!appointmentEnabled) {
      setAppointmentMessage('当前 Prompt 未开启预约功能。');
      return;
    }
    if (!messages.length) {
      setAppointmentMessage('暂无对话记录，无法生成预约。');
      return;
    }
    setSavingAppointment(true);
    setAppointmentMessage('正在生成预约记录...');
    try {
      const payload = messages.map((message) => ({
        role: message.role,
        text: message.content,
        timestamp: message.timestamp,
      }));
      await createAppointmentFromConversation(payload);
      setAppointmentMessage('预约记录已生成，前往「预约记录」标签查看。');
      autoAppointmentTriggeredRef.current = true;
    } catch (error) {
      console.error('WebSocket 生成预约失败', error);
      setAppointmentMessage('生成预约记录失败，请稍后再试。');
    } finally {
      setSavingAppointment(false);
    }
  }, [appointmentEnabled, messages]);

  const maybeTriggerAutoAppointment = useCallback(
    (content: string) => {
      if (!appointmentEnabled || autoAppointmentTriggeredRef.current) return;
      if (containsClosingPhrase(content)) {
        autoAppointmentTriggeredRef.current = true;
        void handleCreateAppointment();
      }
    },
    [appointmentEnabled, handleCreateAppointment],
  );

  const ensureAssistantMessage = useCallback((responseId: string) => {
    const existing = responseMessageMapRef.current[responseId];
    if (existing) {
      return existing;
    }
    const messageId = `assistant-${responseId}`;
    responseMessageMapRef.current[responseId] = messageId;
    const timestamp = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      {
        id: messageId,
        role: 'assistant',
        content: '',
        timestamp,
        streaming: true,
      },
    ]);
    return messageId;
  }, []);

  const appendAssistantDelta = useCallback(
    (responseId: string, delta: string) => {
      if (!delta) return;
      const targetId = ensureAssistantMessage(responseId);
      responseContentRef.current[responseId] = (responseContentRef.current[responseId] ?? '') + delta;
      setMessages((prev) =>
        prev.map((message) =>
          message.id === targetId
            ? {
                ...message,
                content: message.content + delta,
              }
            : message,
        ),
      );
    },
    [ensureAssistantMessage],
  );

  const finalizeAssistantMessage = useCallback(
    (responseId?: string) => {
      if (!responseId) return;
      const messageId = responseMessageMapRef.current[responseId];
      if (!messageId) return;
      const finalText = responseContentRef.current[responseId];
      delete responseContentRef.current[responseId];
      setMessages((prev) =>
        prev.map((message) =>
          message.id === messageId
            ? {
                ...message,
                streaming: false,
                timestamp: new Date().toISOString(),
              }
            : message,
        ),
      );
      delete responseMessageMapRef.current[responseId];
      setAssistantTyping(false);
      if (finalText) {
        void speakText(finalText);
        maybeTriggerAutoAppointment(finalText);
      }
    },
    [maybeTriggerAutoAppointment, speakText],
  );

  const handleRealtimeFrame = useCallback(
    (payload: string) => {
      if (!payload) return;
      try {
        const message = JSON.parse(payload);
        switch (message.type) {
          case 'response.created': {
            const responseId = message.response?.id as string | undefined;
            if (responseId) {
              pendingResponseRef.current = responseId;
              ensureAssistantMessage(responseId);
              setAssistantTyping(true);
            }
            break;
          }
          case 'response.output_text.delta':
          case 'response.text.delta': {
            const responseId = (message.response_id as string | undefined) ?? pendingResponseRef.current;
            const delta = getTextDelta(message);
            if (responseId && delta) {
              appendAssistantDelta(responseId, delta);
            }
            break;
          }
          case 'response.output_text.done':
          case 'response.text.done':
          case 'response.completed':
          case 'response.done': {
            const responseId =
              (message.response?.id as string | undefined) ??
              (message.response_id as string | undefined) ??
              pendingResponseRef.current;
            if (responseId) {
              finalizeAssistantMessage(responseId);
              pendingResponseRef.current = null;
            }
            break;
          }
          case 'response.error': {
            const detail = (message.error?.message as string | undefined) ?? 'Realtime 响应错误';
            setSessionError(detail);
            setAssistantTyping(false);
            pendingResponseRef.current = null;
            break;
          }
          default:
            break;
        }
      } catch (error) {
        console.error('解析 Realtime 帧失败', error, payload);
      }
    },
    [appendAssistantDelta, ensureAssistantMessage, finalizeAssistantMessage],
  );

  const connectRealtime = useCallback(async () => {
    setConnectionState('connecting');
    setSessionError(null);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const session = await createRealtimeSession({
        instructions,
        model: activeModel,
        voice: activeVoice,
        channel: 'websocket',
      });
      const secret = session.client_secret;
      if (!secret) {
        throw new Error('Realtime 服务返回的临时密钥为空');
      }
      setSessionMeta({ id: session.session_id, model: session.model, expires_at: session.expires_at });
      const websocketUrl = session.websocket_url ?? `wss://api.openai.com/v1/realtime?model=${encodeURIComponent(session.model)}`;
      const ws = new WebSocket(websocketUrl, [
        'realtime',
        `openai-insecure-api-key.${secret}`,
        'openai-beta.realtime-v1',
      ]);

      ws.onopen = () => {
        setConnectionState('connected');
      };
      ws.onclose = (event) => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (manualCloseRef.current) {
          manualCloseRef.current = false;
          setConnectionState('idle');
          setSessionError(null);
          setSessionMeta(null);
        } else {
          setConnectionState('error');
          setSessionError(event.reason || 'Realtime 会话已断开');
        }
      };
      ws.onerror = (event) => {
        console.error('Realtime WS error', event);
        setConnectionState('error');
        setSessionError('Realtime 通道异常，请稍后重试');
      };
      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          handleRealtimeFrame(event.data);
        } else if (event.data instanceof ArrayBuffer) {
          const decoded = new TextDecoder().decode(event.data);
          handleRealtimeFrame(decoded);
        } else if (event.data instanceof Blob) {
          event.data.text().then(handleRealtimeFrame).catch((error) => console.error('读取 Realtime Blob 失败', error));
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('初始化 Realtime 失败', error);
      setConnectionState('error');
      setSessionError(error instanceof Error ? error.message : '无法连接 Realtime 服务');
    }
  }, [activeModel, activeVoice, handleRealtimeFrame, instructions]);

  const disconnectSession = useCallback(() => {
    manualCloseRef.current = true;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    responseMessageMapRef.current = {};
    responseContentRef.current = {};
    pendingResponseRef.current = null;
    setMessages([]);
    setAssistantTyping(false);
    setSessionMeta(null);
    setSessionError(null);
    setConnectionState('idle');
    autoAppointmentTriggeredRef.current = false;
    setAppointmentMessage(null);
  }, []);

  const clearConversation = useCallback(() => {
    responseMessageMapRef.current = {};
    responseContentRef.current = {};
    pendingResponseRef.current = null;
    setMessages([]);
    setAssistantTyping(false);
    setAppointmentMessage(null);
    autoAppointmentTriggeredRef.current = false;
  }, []);

  const sendConversationItem = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setSessionError('Realtime 通道未连接，无法发送消息');
      return false;
    }
    ws.send(
      JSON.stringify({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'user',
          content: [
            {
              type: 'input_text',
              text,
            },
          ],
        },
      }),
    );
    return true;
  }, []);

  const requestAssistantReply = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setSessionError('Realtime 通道未连接，无法发送消息');
      return;
    }
    ws.send(
      JSON.stringify({
        type: 'response.create',
        response: {
          modalities: ['text'],
        },
      }),
    );
    setAssistantTyping(true);
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isAssistantTyping || connectionState !== 'connected') return;

    const timestamp = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: `user-${timestamp}`,
      role: 'user',
      content: trimmed,
      timestamp,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    const sent = sendConversationItem(trimmed);
    if (sent && autoReply) {
      requestAssistantReply();
    }
  };

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    autoAppointmentTriggeredRef.current = false;
    setAppointmentMessage(null);
  }, [prompt?.id]);

  useEffect(() => {
    return () => {
      if (ttsAudioUrl) {
        URL.revokeObjectURL(ttsAudioUrl);
      }
    };
  }, [ttsAudioUrl]);

  useEffect(() => {
    const container = historyRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!ttsEnabled) {
      setTtsStatus(null);
    }
  }, [ttsEnabled]);

  useEffect(() => {
    const providerModels = ttsModelOptions[ttsProvider];
    setTtsModel((prev) => {
      if (providerModels.some((option) => option.id === prev)) {
        return prev;
      }
      return providerModels[0]?.id ?? prev;
    });
  }, [ttsProvider]);

  useEffect(() => {
    if (ttsProvider === 'google') {
      const voices = getGoogleVoices(ttsLanguage);
      setTtsVoice((prev) => {
        if (voices.some((option) => option.id === prev)) {
          return prev;
        }
        return voices[0]?.id ?? prev;
      });
    } else {
      setTtsVoice((prev) => {
        if (openAiVoiceOptions.some((option) => option.id === prev)) {
          return prev;
        }
        return openAiVoiceOptions[0].id;
      });
    }
  }, [ttsLanguage, ttsProvider]);

  useEffect(() => {
    setTtsSpeakingRate(1);
    setTtsPitch(0);
  }, [ttsProvider]);

  const stats = useMemo(() => {
    const userTurns = messages.filter((message) => message.role === 'user').length;
    const assistantTurns = messages.filter((message) => message.role === 'assistant').length;
    return {
      totalTurns: messages.length,
      userTurns,
      assistantTurns,
      lastUpdated: messages[messages.length - 1]?.timestamp,
    };
  }, [messages]);

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
  };

  const toggleAutoReply = () => {
    setAutoReply((prev) => !prev);
  };

  const connectionSummary = connectionTagMap[connectionState];
  const displayModel = sessionMeta?.model ?? activeModel;
  const providerModelOptions = ttsModelOptions[ttsProvider];
  const providerVoiceOptions = useMemo(() => {
    if (ttsProvider === 'google') {
      return getGoogleVoices(ttsLanguage);
    }
    return openAiVoiceOptions;
  }, [ttsLanguage, ttsProvider]);

  return (
    <div className="ws-console">
      <div className="ws-console__main">
        <Tile className="ws-status-card">
          <div className="ws-status-card__info">
            <Tag type={connectionSummary.type} size="sm">
              {connectionSummary.label}
            </Tag>
            <div>
              <h4>{prompt?.name ?? '默认 Prompt'}</h4>
              <p>
                模型：{displayModel} · Session：{sessionMeta?.id ?? '尚未建立'}
              </p>
            </div>
          </div>
          <div className="ws-status-card__actions">
            <Button
              kind="primary"
              size="sm"
              onClick={() => {
                void connectRealtime();
              }}
              disabled={connectionState === 'connecting' || connectionState === 'connected'}
            >
              建立连接
            </Button>
            <Button
              kind="ghost"
              size="sm"
              onClick={disconnectSession}
              disabled={connectionState !== 'connected' && connectionState !== 'connecting'}
            >
              断开
            </Button>
            <Button kind="ghost" size="sm" onClick={clearConversation} disabled={messages.length === 0}>
              清空对话
            </Button>
            {sessionError && <span className="ws-status-card__error">{sessionError}</span>}
          </div>
        </Tile>
        <div className="ws-console__grid">
          <Tile className="ws-chat-panel">
            <div className="chat-history" ref={historyRef}>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`chat-bubble ${message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}
                >
                  <div className="chat-meta">
                    <Tag type={message.role === 'user' ? 'blue' : 'purple'} size="sm">
                      {message.role === 'user' ? '我' : '机器人'}
                    </Tag>
                    <span>{formatTime(message.timestamp)}</span>
                    {message.streaming && message.role === 'assistant' && (
                      <InlineLoading status="active" description="生成中" />
                    )}
                  </div>
                  <div className="chat-content">{message.content}</div>
                </div>
              ))}
              {isAssistantTyping && !messages.some((msg) => msg.streaming) && (
                <div className="chat-bubble chat-bubble-assistant">
                  <div className="chat-meta">
                    <Tag type="purple" size="sm">
                      机器人
                    </Tag>
                    <InlineLoading status="active" description="思考中" />
                  </div>
                </div>
              )}
            </div>
          </Tile>
          <Tile className="ws-input-panel">
            <form className="chat-input-form" onSubmit={handleSubmit}>
              <TextArea
                id="test-chat-input"
                labelText="输入测试内容"
                placeholder="例如：请模拟客户提出异议，并帮我迭代回答。"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                rows={5}
                disabled={connectionState !== 'connected'}
              />
              <div className="chat-actions">
                {!autoReply && (
                  <Button
                    kind="secondary"
                    type="button"
                    onClick={requestAssistantReply}
                    disabled={connectionState !== 'connected'}
                  >
                    让机器人回复
                  </Button>
                )}
                <Button type="submit" disabled={!input.trim() || connectionState !== 'connected' || isAssistantTyping}>
                  发送
                </Button>
              </div>
            </form>
            <div className="ws-quick-prompts">
              <span>快捷提示</span>
              <div className="ws-quick-prompts__chips">
                {quickPrompts.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="ws-quick-prompts__chip"
                    onClick={() => handleQuickPrompt(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </Tile>
        </div>
      </div>
      <div className="ws-console__side">
        <Tile className="session-panel">
          <div>
            <h3>会话状态</h3>
            <p className="session-panel__helper">在这里查看实时连接与轮次情况，可随时切换自动回复。</p>
          </div>
          <dl className="session-meta">
            <dt>会话 ID</dt>
            <dd>{sessionMeta?.id ?? '尚未建立'}</dd>
            <dt>连接状态</dt>
            <dd>{connectionSummary.label}</dd>
            <dt>Session 失效</dt>
            <dd>{sessionMeta?.expires_at ? formatTime(sessionMeta.expires_at) : '--:--'}</dd>
            <dt>总轮次</dt>
            <dd>{stats.totalTurns}</dd>
            <dt>用户消息</dt>
            <dd>{stats.userTurns}</dd>
            <dt>机器人回复</dt>
            <dd>{stats.assistantTurns}</dd>
            <dt>最近更新时间</dt>
            <dd>{formatTime(stats.lastUpdated)}</dd>
          </dl>
          <Toggle
            id="auto-reply-toggle"
            labelText="机器人自动回复"
            labelA="关闭"
            labelB="开启"
            toggled={autoReply}
            onToggle={toggleAutoReply}
          />
        </Tile>
        <Tile className="session-panel">
          <div>
            <h3>语音配置</h3>
            <p className="session-panel__helper">这里仅控制文本转语音，聊天模型始终跟随 Prompt 设置。</p>
          </div>
          <Select
            id="tts-provider-selector"
            labelText="TTS 服务商"
            value={ttsProvider}
            onChange={(event) => setTtsProvider(event.target.value as (typeof ttsProviderOptions)[number]['id'])}
          >
            {ttsProviderOptions.map((provider) => (
              <SelectItem key={provider.id} value={provider.id} text={provider.label} />
            ))}
          </Select>
          {ttsProvider === 'google' && (
            <Select
              id="tts-language-selector"
              labelText="语言"
              value={ttsLanguage}
              onChange={(event) => setTtsLanguage(event.target.value)}
              disabled={!ttsEnabled}
            >
              {googleLanguageOptions.map((language) => (
                <SelectItem key={language.code} value={language.code} text={`${language.label} · ${language.code}`} />
              ))}
            </Select>
          )}
          <Toggle
            id="tts-enable-toggle"
            labelText="启用文本转语音"
            labelA="关闭"
            labelB="开启"
            toggled={ttsEnabled}
            onToggle={() => setTtsEnabled((prev) => !prev)}
          />
          <Select
            id="tts-model-selector"
            labelText="TTS 模型"
            value={ttsModel}
            onChange={(event) => setTtsModel(event.target.value)}
            disabled={!ttsEnabled}
          >
            {providerModelOptions.map((option) => (
              <SelectItem key={option.id} value={option.id} text={option.label} />
            ))}
          </Select>
          <Select
            id="tts-voice-selector"
            labelText="TTS 声音"
            value={ttsVoice}
            onChange={(event) => setTtsVoice(event.target.value)}
            disabled={!ttsEnabled}
          >
            {providerVoiceOptions.map((voice) => (
              <SelectItem key={voice.id} value={voice.id} text={voice.label} />
            ))}
          </Select>
          {ttsProvider === 'google' && (
            <>
              <NumberInput
                id="tts-speaking-rate"
                label="语速（0.25 ~ 4.0）"
                min={0.25}
                max={4}
                step={0.1}
                value={ttsSpeakingRate}
                onChange={(_, { value }) => {
                  const parsed = Number(value);
                  if (!Number.isNaN(parsed)) {
                    setTtsSpeakingRate(Math.min(4, Math.max(0.25, parsed)));
                  }
                }}
                disabled={!ttsEnabled}
              />
              <NumberInput
                id="tts-pitch"
                label="音调（-20 ~ 20 半音）"
                min={-20}
                max={20}
                step={0.5}
                value={ttsPitch}
                onChange={(_, { value }) => {
                  const parsed = Number(value);
                  if (!Number.isNaN(parsed)) {
                    setTtsPitch(Math.min(20, Math.max(-20, parsed)));
                  }
                }}
                disabled={!ttsEnabled}
              />
            </>
          )}
          <div className="tts-audio-panel">
            <p className="session-panel__helper">{ttsStatus ?? '关闭后仅输出文本，启用后可试听语音。'}</p>
            <audio ref={ttsAudioRef} controls className="tts-audio-player" />
          </div>
        </Tile>
        {appointmentEnabled && (
          <Tile className="session-panel">
            <div>
              <h3>预约记录</h3>
              <p className="session-panel__helper">将当前对话整理成预约摘要并写入后端记录。</p>
            </div>
            {appointmentMessage && <p className="session-panel__helper">{appointmentMessage}</p>}
            <Button
              kind="primary"
              onClick={handleCreateAppointment}
              disabled={!messages.length || savingAppointment || connectionState === 'connecting'}
            >
              {savingAppointment ? '生成中...' : '生成预约记录'}
            </Button>
          </Tile>
        )}
      </div>
    </div>
  );
}
