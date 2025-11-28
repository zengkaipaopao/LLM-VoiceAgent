import { http } from './http';

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type ChatResponse = {
  model_id: string;
  reply: string;
};

export async function sendChat(modelId: string, messages: ChatMessage[]) {
  const response = await http.post<ChatResponse>('/chat', {
    model_id: modelId,
    messages,
  });
  return response.data;
}
