/**
 * Chat API client.
 * 
 * Provides methods for interacting with the LLM chat backend.
 */

const API_BASE = '/api/v1';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  message: string;
  template_code?: string;
  provider?: string;
  model?: string;
  call_id?: string;
  temperature?: number;
}

export interface ChatResponse {
  response: string;
  call_id: string;
  tokens_used?: number;
}

export interface ExtractionRequest {
  call_id: string;
  template_code?: string;
}

export interface ExtractionResponse {
  success: boolean;
  appointment_id?: string;
  extracted_data: Record<string, any>;
  confidence: number;
  message: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  code: string;
  description?: string;
  category?: string;
  system_prompt: string;
  extraction_schema?: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateListResponse {
  templates: PromptTemplate[];
  total: number;
}

/**
 * Send a chat message and get response.
 */
export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Chat request failed');
  }

  return response.json();
}

/**
 * Stream chat messages using Server-Sent Events.
 */
export async function* streamMessage(request: ChatRequest): AsyncGenerator<{
  type: 'call_id' | 'content' | 'done' | 'error';
  content?: string;
  call_id?: string;
  error?: string;
}> {
  const response = await fetch(`${API_BASE}/chat/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error('Stream request failed');
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error('No response body');
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          yield data;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Extract appointment from conversation.
 */
export async function extractAppointment(
  request: ExtractionRequest
): Promise<ExtractionResponse> {
  const response = await fetch(`${API_BASE}/chat/extract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Extraction failed');
  }

  return response.json();
}

/**
 * List all prompt templates.
 */
export async function listTemplates(
  category?: string
): Promise<PromptTemplateListResponse> {
  const url = new URL(`${API_BASE}/prompt-templates/templates`, window.location.origin);
  if (category) {
    url.searchParams.set('category', category);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error('Failed to fetch templates');
  }

  return response.json();
}

/**
 * Get a specific template by code.
 */
export async function getTemplate(code: string): Promise<PromptTemplate> {
  const response = await fetch(`${API_BASE}/prompt-templates/templates/${code}`);

  if (!response.ok) {
    throw new Error(`Template '${code}' not found`);
  }

  return response.json();
}
