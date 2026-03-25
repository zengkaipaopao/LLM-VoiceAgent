import { useState, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../api/http';

/**
 * Message 接口
 */
export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

/**
 * Chat 请求参数
 */
interface ChatRequest {
  message: string;
  template_code: string;
  provider?: string;
  model?: string;
  temperature?: number;
  call_id?: string;
}

/**
 * SSE 事件类型
 */
interface SSEEvent {
  type: 'call_id' | 'content' | 'done' | 'error';
  call_id?: string;
  content?: string;
  error?: string;
  tokens_used?: number;
}

function parseSSEEvent(rawEvent: string): SSEEvent | null {
  const dataLines = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (!dataLines.length) {
    return null;
  }

  const payload = dataLines.join('\n').trim();
  if (!payload) {
    return null;
  }

  try {
    return JSON.parse(payload) as SSEEvent;
  } catch {
    return null;
  }
}

/**
 * useChatStream Hook 返回值
 */
interface UseChatStreamReturn {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  callId: string | null;
  totalTokens: number;
  sendMessage: (content: string, options?: Partial<ChatRequest>) => Promise<void>;
  retryLastMessage: () => Promise<void>;
  dismissError: () => void;
  clearMessages: () => void;
}

/**
 * useChatStream - 处理 LLM 对话流式响应的自定义 Hook
 */
export function useChatStream(
  defaultProvider?: string,
  defaultTemplate: string = 'general_appointment'
): UseChatStreamReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState<string | null>(null);
  const [totalTokens, setTotalTokens] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastOptionsRef = useRef<Partial<ChatRequest>>({});

  /**
   * 发送消息并处理流式响应
   */
  const sendMessage = useCallback(async (
    content: string,
    options: Partial<ChatRequest> = {}
  ) => {
    // 保存选项用于重试
    lastOptionsRef.current = options;

    // 清除之前的错误
    setError(null);
    setIsLoading(true);

    // 添加用户消息到历史
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    // 创建 AbortController 用于取消请求
    abortControllerRef.current = new AbortController();

    try {
      // 构建请求体
      const requestBody: ChatRequest = {
        message: content,
        template_code: options.template_code || defaultTemplate,
        provider: options.provider ?? defaultProvider,
        model: options.model,
        temperature: options.temperature,
        call_id: options.call_id || callId || undefined
      };

      // 发起 SSE 请求并处理流
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No readable stream available');
      }

      // 创建临时的 assistant 消息
      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, assistantMessage]);

      let assistantContent = '';
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();

        const decodedChunk = decoder.decode(value || new Uint8Array(), { stream: !done });
        buffer += decodedChunk.replace(/\r\n/g, '\n');

        let boundaryIndex = buffer.indexOf('\n\n');
        while (boundaryIndex !== -1) {
          const rawEvent = buffer.slice(0, boundaryIndex);
          buffer = buffer.slice(boundaryIndex + 2);

          const eventResp = parseSSEEvent(rawEvent);
          if (eventResp) {
            if (eventResp.type === 'call_id' && eventResp.call_id) {
              setCallId(eventResp.call_id);
            } else if (eventResp.type === 'content' && typeof eventResp.content === 'string') {
              assistantContent += eventResp.content;
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages[newMessages.length - 1] = {
                  ...assistantMessage,
                  content: assistantContent
                };
                return newMessages;
              });
            } else if (eventResp.type === 'error') {
              throw new Error(eventResp.error || 'Server stream error');
            } else if (eventResp.type === 'done' && typeof eventResp.tokens_used === 'number') {
              setTotalTokens(prev => prev + eventResp.tokens_used);
            }
          }

          boundaryIndex = buffer.indexOf('\n\n');
        }

        if (done) {
          const lastEvent = parseSSEEvent(buffer);
          if (lastEvent?.type === 'error') {
            throw new Error(lastEvent.error || 'Server stream error');
          }
          if (lastEvent?.type === 'done' && typeof lastEvent.tokens_used === 'number') {
            setTotalTokens(prev => prev + lastEvent.tokens_used);
          }
          break;
        }
      }

      setIsLoading(false);

    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Request aborted');
      } else {
        const errorMessage = err.message || 'Failed to send message';
        setError(errorMessage);
        
        // 添加错误消息
        const errorMsg: Message = {
          role: 'assistant',
          content: `❌ 错误: ${errorMessage}`,
          timestamp: new Date()
        };
        setMessages(prev => {
          const newMessages = [...prev];
          const last = newMessages[newMessages.length - 1];
          if (last?.role === 'assistant' && !last.content) {
            newMessages.pop();
          }
          return [...newMessages, errorMsg];
        });
      }
      setIsLoading(false);
    }
  }, [callId, defaultProvider, defaultTemplate]);

  /**
   * 重试上一条消息
   */
  const retryLastMessage = useCallback(async () => {
    // 找到最后一条用户消息
    const lastUserMessage = messages.slice().reverse().find(m => m.role === 'user');
    if (!lastUserMessage) return;

    // 移除最后一条错误消息(如果有)和用户消息
    setMessages(prev => {
      const newMessages = [...prev];
      // 如果最后一条是错误消息或助手的部分回复,移除它
      if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
        newMessages.pop();
      }
      // 移除最后一条用户消息(因为 sendMessage 会重新添加)
      if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'user') {
        newMessages.pop();
      }
      return newMessages;
    });

    // 重新发送
    await sendMessage(lastUserMessage.content, lastOptionsRef.current);
  }, [messages, sendMessage]);

  /**
   * 清除所有消息
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setCallId(null);
    setError(null);
    setTotalTokens(0);
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  /**
   * 清除错误
   */
  const dismissError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    sendMessage,
    retryLastMessage,
    dismissError,
    clearMessages
  };
}
