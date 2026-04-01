import type { Message } from './types';

export function createUserMessage(content: string): Message {
  return {
    role: 'user',
    content,
    timestamp: new Date(),
  };
}

export function createAssistantMessage(content: string = ''): Message {
  return {
    role: 'assistant',
    content,
    timestamp: new Date(),
  };
}

export function createAssistantErrorMessage(errorMessage: string): Message {
  return {
    role: 'assistant',
    content: `❌ 错误: ${errorMessage}`,
    timestamp: new Date(),
  };
}

export function replaceLastMessage(messages: Message[], nextMessage: Message): Message[] {
  if (!messages.length) {
    return [nextMessage];
  }

  const next = [...messages];
  next[next.length - 1] = nextMessage;
  return next;
}

export function removeTrailingEmptyAssistantMessage(messages: Message[]): Message[] {
  if (!messages.length) {
    return messages;
  }

  const next = [...messages];
  const last = next[next.length - 1];
  if (last.role === 'assistant' && !last.content) {
    next.pop();
  }
  return next;
}
