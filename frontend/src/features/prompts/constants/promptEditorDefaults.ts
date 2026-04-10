import { DEFAULT_GENERATE_MODEL } from '../../../config/llmModels';
import { PromptFormValues, PromptTemplate } from '../../../types/shared';

export const defaultPromptFormValues: PromptFormValues = {
  name: '',
  code: '',
  description: '',
  category: 'booking',
  llmProvider: 'gemini',
  llmModel: DEFAULT_GENERATE_MODEL,
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
  extractionPrompt: '',
  extractionSchema: '',
  responseFormat: 'text',
  outputSchema: '',
  voiceProvider: '',
  voiceId: '',
  twilioInboundNumbers: '',
  isTwilioIncomingDefault: false,
};

export function buildPromptFormValues(prompt?: PromptTemplate): PromptFormValues {
  if (!prompt) {
    return { ...defaultPromptFormValues };
  }

  return {
    name: prompt.name,
    code: prompt.code,
    description: prompt.description || '',
    category: prompt.category || 'booking',
    llmProvider: prompt.llmProvider,
    llmModel: prompt.llmModel,
    temperature: prompt.temperature,
    maxTokens: prompt.maxTokens,
    systemPrompt: prompt.systemPrompt,
    extractionPrompt: prompt.extractionPrompt || '',
    extractionSchema: prompt.extractionSchema ? JSON.stringify(prompt.extractionSchema, null, 2) : '',
    responseFormat: prompt.responseFormat || 'text',
    outputSchema: prompt.outputSchema
      ? JSON.stringify(prompt.outputSchema, null, 2)
      : prompt.extractionSchema
        ? JSON.stringify(prompt.extractionSchema, null, 2)
        : '',
    voiceProvider: prompt.voiceProvider || '',
    voiceId: prompt.voiceId || '',
    twilioInboundNumbers: (prompt.twilioInboundNumbers || []).join('\n'),
    isTwilioIncomingDefault: prompt.isTwilioIncomingDefault || false,
  };
}
