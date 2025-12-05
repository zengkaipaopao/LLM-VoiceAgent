import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, InlineLoading, Tag, TextArea, Tile, Toggle } from '@carbon/react';
import { createRealtimeSession } from '../../../api/realtime';
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

type WebSocketConsoleProps = {
  prompt?: PromptTemplate;
};

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
  const pendingResponseRef = useRef<string | null>(null);
  const instructions = prompt?.systemPrompt ?? defaultInstructions;
  const activeModel = prompt?.modelId ?? fallbackModel;

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
    },
    [],
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
          case 'response.output_text.delta': {
            const responseId = (message.response_id as string | undefined) ?? pendingResponseRef.current;
            const delta = getTextDelta(message);
            if (responseId && delta) {
              appendAssistantDelta(responseId, delta);
            }
            break;
          }
          case 'response.output_text.done':
          case 'response.completed': {
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
      const session = await createRealtimeSession({ instructions, model: activeModel });
      const secret = session.client_secret;
      if (!secret) {
        throw new Error('Realtime 服务返回的临时密钥为空');
      }
      setSessionMeta({ id: session.session_id, model: session.model, expires_at: session.expires_at });
      const websocketUrl = session.websocket_url ?? `wss://api.openai.com/v1/realtime?model=${encodeURIComponent(session.model)}`;
      const ws = new WebSocket(websocketUrl, [
        'realtime',
        `openai-insecure-session.${secret}`,
        'openai-beta.realtime-v1',
      ]);

      ws.onopen = () => {
        setConnectionState('connected');
      };
      ws.onclose = (event) => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        setConnectionState('error');
        setSessionError(event.reason || 'Realtime 会话已断开');
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
  }, [activeModel, handleRealtimeFrame, instructions]);

  const resetConversation = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    responseMessageMapRef.current = {};
    pendingResponseRef.current = null;
    setMessages([]);
    setAssistantTyping(false);
    void connectRealtime();
  }, [connectRealtime]);

  const sendUserMessage = useCallback((text: string, triggerResponse: boolean) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setSessionError('Realtime 通道未连接，无法发送消息');
      return;
    }
    const payload = {
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
    };
    ws.send(JSON.stringify(payload));

    if (triggerResponse) {
      ws.send(JSON.stringify({ type: 'response.create' }));
      setAssistantTyping(true);
    }
  }, []);

  const requestAssistantReply = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setSessionError('Realtime 通道未连接');
      return;
    }
    ws.send(JSON.stringify({ type: 'response.create' }));
    setAssistantTyping(true);
  }, []);

  useEffect(() => {
    void connectRealtime();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectRealtime]);

  useEffect(() => {
    const container = historyRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages]);

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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isAssistantTyping) return;

    const timestamp = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${timestamp}`,
        role: 'user',
        content: trimmed,
        timestamp,
      },
    ]);
    setInput('');
    sendUserMessage(trimmed, autoReply);
  };

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
  };

  const toggleAutoReply = () => {
    setAutoReply((prev) => !prev);
  };

  const connectionSummary = connectionTagMap[connectionState];
  const displayModel = sessionMeta?.model ?? activeModel;

  return (
    <div className="test-console">
      <div className="test-console__column">
        <Tile className="chat-panel">
          <div className="chat-panel__header">
            <Tag type={connectionSummary.type} size="sm">
              {connectionSummary.label}
            </Tag>
            <span className="chat-panel__helper">
              模型：{displayModel} · Prompt：{prompt?.name ?? '默认 Prompt'} · Session：
              {sessionMeta?.id ?? '尚未建立'}
            </span>
          </div>
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
        <Tile>
          <form className="chat-input-form" onSubmit={handleSubmit}>
            <TextArea
              id="test-chat-input"
              labelText="你想让机器人做什么？"
              placeholder="例如：请模拟客户提出异议，并帮我迭代回答。"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={4}
              disabled={connectionState !== 'connected'}
            />
            <div className="chat-actions">
              <Button kind="ghost" type="button" onClick={resetConversation}>
                重新开始
              </Button>
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
          <div className="quick-prompts">
            <span className="quick-prompts__label">快捷输入</span>
            <div className="quick-prompts__list">
              {quickPrompts.map((prompt) => (
                <Button key={prompt} kind="tertiary" size="sm" type="button" onClick={() => handleQuickPrompt(prompt)}>
                  {prompt}
                </Button>
              ))}
            </div>
          </div>
        </Tile>
      </div>
      <div className="test-console__column">
        <Tile className="session-panel">
          <div>
            <h3>会话状态</h3>
            <p className="session-panel__helper">使用该面板跟踪实时连接、自动回复策略与多轮对话指标。</p>
            {sessionError && <p className="session-panel__error">{sessionError}</p>}
          </div>
          <dl className="session-meta">
            <dt>会话 ID</dt>
            <dd>{sessionMeta?.id ?? '尚未建立'}</dd>
            <dt>模型</dt>
            <dd>{activeModel}</dd>
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
      </div>
    </div>
  );
}
