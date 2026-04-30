import { API_BASE_URL, buildApiRequestHeaders } from '../../api/http';
import { parseSSEEvent, sanitizeAssistantPrefix } from './streamUtils';

interface StreamUnifiedChatResponseOptions {
  callId: string;
  message: string;
  templateCode: string;
  provider?: string;
  model?: string;
  signal: AbortSignal;
  requestFailedWithStatusMessage: (status: number) => string;
  streamFailedMessage: string;
  onSessionCallId: (callId: string) => void;
  onAssistantContent: (content: string) => void;
  onTokensUsed: (tokens: number) => void;
}

export async function streamUnifiedChatResponse({
  callId,
  message,
  templateCode,
  provider,
  model,
  signal,
  requestFailedWithStatusMessage,
  streamFailedMessage,
  onSessionCallId,
  onAssistantContent,
  onTokensUsed,
}: StreamUnifiedChatResponseOptions): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: buildApiRequestHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }),
    body: JSON.stringify({
      call_id: callId,
      message,
      template_code: templateCode,
      provider,
      model,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(requestFailedWithStatusMessage(response.status));
  }

  const reader = response.body.getReader();
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
          onSessionCallId(eventPayload.call_id);
        }

        if (eventPayload.type === 'content' && typeof eventPayload.content === 'string') {
          assistantContent += eventPayload.content;
          onAssistantContent(sanitizeAssistantPrefix(assistantContent));
        }

        if (eventPayload.type === 'done' && typeof eventPayload.tokens_used === 'number') {
          onTokensUsed(eventPayload.tokens_used);
        }

        if (eventPayload.type === 'error') {
          throw new Error(eventPayload.error || streamFailedMessage);
        }
      }

      boundaryIndex = buffer.indexOf('\n\n');
    }

    if (done) {
      const tailEvent = parseSSEEvent(buffer);
      if (tailEvent?.type === 'error') {
        throw new Error(tailEvent.error || streamFailedMessage);
      }
      if (tailEvent?.type === 'done' && typeof tailEvent.tokens_used === 'number') {
        onTokensUsed(tailEvent.tokens_used);
      }
      break;
    }
  }
}
