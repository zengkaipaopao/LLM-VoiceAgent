import { API_BASE_URL } from '../../api/http';
import { sanitizeAssistantPrefix } from '../unifiedTestLab/streamUtils';
import { parseSSEEvent } from './sse';
import type { ChatRequest } from './types';

interface StreamChatResponseOptions {
  requestBody: ChatRequest;
  signal: AbortSignal;
  onCallId: (callId: string) => void;
  onAssistantContent: (content: string) => void;
  onTokensUsed: (tokensUsed: number) => void;
}

export async function streamChatResponse({
  requestBody,
  signal,
  onCallId,
  onAssistantContent,
  onTokensUsed,
}: StreamChatResponseOptions): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(requestBody),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No readable stream available');
  }

  const decoder = new TextDecoder();
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

      const eventPayload = parseSSEEvent(rawEvent);
      if (eventPayload) {
        if (eventPayload.type === 'call_id' && eventPayload.call_id) {
          onCallId(eventPayload.call_id);
        }

        if (eventPayload.type === 'content' && typeof eventPayload.content === 'string') {
          assistantContent += eventPayload.content;
          onAssistantContent(sanitizeAssistantPrefix(assistantContent));
        }

        if (eventPayload.type === 'error') {
          throw new Error(eventPayload.error || 'Server stream error');
        }

        if (eventPayload.type === 'done' && typeof eventPayload.tokens_used === 'number') {
          onTokensUsed(eventPayload.tokens_used);
        }
      }

      boundaryIndex = buffer.indexOf('\n\n');
    }

    if (done) {
      const tailEvent = parseSSEEvent(buffer);
      if (tailEvent?.type === 'error') {
        throw new Error(tailEvent.error || 'Server stream error');
      }
      if (tailEvent?.type === 'done' && typeof tailEvent.tokens_used === 'number') {
        onTokensUsed(tailEvent.tokens_used);
      }
      break;
    }
  }
}
