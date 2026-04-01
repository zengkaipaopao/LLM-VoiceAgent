export type StreamEvent = {
  type: 'call_id' | 'content' | 'done' | 'error';
  call_id?: string;
  content?: string;
  error?: string;
  tokens_used?: number;
};

export function sanitizeAssistantPrefix(text: string): string {
  return text.replace(
    /^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*/i,
    ''
  );
}

export function parseSSEEvent(rawEvent: string): StreamEvent | null {
  const dataLines = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (!dataLines.length) return null;

  const payload = dataLines.join('\n').trim();
  if (!payload) return null;

  try {
    return JSON.parse(payload) as StreamEvent;
  } catch {
    return null;
  }
}

export function resolveErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: unknown }).response === 'object'
  ) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    if (typeof response?.data?.detail === 'string') {
      return response.data.detail;
    }
  }
  return fallback;
}
