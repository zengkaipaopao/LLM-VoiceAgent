import type { SSEEvent } from './types';

export function parseSSEEvent(rawEvent: string): SSEEvent | null {
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
