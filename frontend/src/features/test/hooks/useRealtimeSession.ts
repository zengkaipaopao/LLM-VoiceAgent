import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { createRealtimeSession } from '../../../api/realtime';
import { ChatMessage, ConnectionState, RealtimeSessionMeta } from '../components/websocket/types';
import { getTextDelta } from '../utils/realtime';

type UseRealtimeSessionParams = {
  instructions: string;
  model: string;
  voice?: string;
  channel?: 'websocket' | 'webrtc' | 'sip';
  onAssistantMessage?: (text: string) => void;
};

export type RealtimeSessionApi = {
  messages: ChatMessage[];
  connectionState: ConnectionState;
  sessionMeta: RealtimeSessionMeta;
  sessionError: string | null;
  isAssistantTyping: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  clearConversation: () => void;
  recordUserMessage: (text: string) => ChatMessage;
  sendUserMessage: (text: string) => boolean;
  requestAssistantReply: () => void;
};

export function useRealtimeSession({
  instructions,
  model,
  voice,
  channel = 'websocket',
  onAssistantMessage,
}: UseRealtimeSessionParams): RealtimeSessionApi {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('idle');
  const [sessionMeta, setSessionMeta] = useState<RealtimeSessionMeta>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isAssistantTyping, setAssistantTyping] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const manualCloseRef = useRef(false);
  const responseMessageMapRef = useRef<Record<string, string>>({});
  const responseContentRef = useRef<Record<string, string>>({});
  const pendingResponseRef = useRef<string | null>(null);

  const recordUserMessage = useCallback((text: string): ChatMessage => {
    const timestamp = new Date().toISOString();
    const message: ChatMessage = {
      id: `user-${timestamp}`,
      role: 'user',
      content: text,
      timestamp,
    };
    setMessages((prev) => [...prev, message]);
    return message;
  }, []);

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
        onAssistantMessage?.(finalText);
      }
    },
    [onAssistantMessage],
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

  const connect = useCallback(async () => {
    setConnectionState('connecting');
    setSessionError(null);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    try {
      const session = await createRealtimeSession({
        instructions,
        model,
        voice,
        channel,
      });
      const secret = session.client_secret;
      if (!secret) {
        throw new Error('Realtime 服务返回的临时密钥为空');
      }
      setSessionMeta({ id: session.session_id, model: session.model, expires_at: session.expires_at });
      const websocketUrl =
        session.websocket_url ?? `wss://api.openai.com/v1/realtime?model=${encodeURIComponent(session.model)}`;
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
  }, [channel, handleRealtimeFrame, instructions, model, voice]);

  const disconnect = useCallback(() => {
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
  }, []);

  const clearConversation = useCallback(() => {
    responseMessageMapRef.current = {};
    responseContentRef.current = {};
    pendingResponseRef.current = null;
    setMessages([]);
    setAssistantTyping(false);
  }, []);

  const sendUserMessage = useCallback((text: string) => {
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

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return useMemo(
    () => ({
      messages,
      connectionState,
      sessionMeta,
      sessionError,
      isAssistantTyping,
      connect,
      disconnect,
      clearConversation,
      recordUserMessage,
      sendUserMessage,
      requestAssistantReply,
    }),
    [
      messages,
      connectionState,
      sessionMeta,
      sessionError,
      isAssistantTyping,
      connect,
      disconnect,
      clearConversation,
      recordUserMessage,
      sendUserMessage,
      requestAssistantReply,
    ],
  );
}
