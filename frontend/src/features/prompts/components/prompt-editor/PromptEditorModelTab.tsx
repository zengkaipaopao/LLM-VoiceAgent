import { NumberInput, Select, SelectItem, Stack, TextArea } from '@carbon/react';
import { LlmModelOption, PromptFormValues } from '../../../../types/shared';

interface PromptEditorModelTabProps {
  form: PromptFormValues;
  models: LlmModelOption[];
  loadingModels: boolean;
  modelLoadError: string | null;
  onChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  t: (key: string) => string;
}

function parseNumberInput(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function PromptEditorModelTab({
  form,
  models,
  loadingModels,
  modelLoadError,
  onChange,
  t,
}: PromptEditorModelTabProps) {
  return (
    <Stack gap={6}>
      <Select
        id="llmProvider"
        labelText={t('prompts.editor.fields.provider')}
        value={form.llmProvider}
        onChange={(event) => onChange('llmProvider', event.target.value)}
      >
        <SelectItem value="gemini" text="Google Gemini" />
        <SelectItem value="openai" text="OpenAI (Planning)" />
        <SelectItem value="claude" text="Anthropic Claude (Planning)" />
      </Select>
      <Select
        id="llmModel"
        labelText={t('prompts.editor.fields.model')}
        value={form.llmModel}
        onChange={(event) => onChange('llmModel', event.target.value)}
        helperText={
          modelLoadError
            ? `模型列表加载失败：${modelLoadError}`
            : '尽可能展示更多官方模型，标签含义：[文本]/[实时]/[文本+实时]/[其他]'
        }
        disabled={loadingModels}
      >
        {models.map((model) => (
          <SelectItem key={model.value} value={model.value} text={model.label} />
        ))}
        {!models.some((model) => model.value === form.llmModel) && form.llmModel && (
          <SelectItem value={form.llmModel} text={`${form.llmModel} (Current)`} />
        )}
      </Select>
      <div style={{ display: 'flex', gap: '1rem' }}>
        <div style={{ flex: 1 }}>
          <NumberInput
            id="temperature"
            label={t('prompts.editor.fields.temperature')}
            min={0}
            max={2}
            step={0.1}
            value={form.temperature}
            onChange={(_, { value }) => onChange('temperature', parseNumberInput(value, form.temperature))}
            invalidText="0-2"
          />
        </div>
        <div style={{ flex: 1 }}>
          <NumberInput
            id="maxTokens"
            label={t('prompts.editor.fields.maxTokens')}
            min={1}
            max={32000}
            step={1}
            value={form.maxTokens}
            onChange={(_, { value }) => onChange('maxTokens', parseNumberInput(value, form.maxTokens))}
          />
        </div>
      </div>

      <Select
        id="responseFormat"
        labelText="Response Format"
        value={form.responseFormat || 'text'}
        onChange={(event) => onChange('responseFormat', event.target.value as PromptFormValues['responseFormat'])}
      >
        <SelectItem value="text" text="Text (Default)" />
        <SelectItem value="json_object" text="JSON Object" />
      </Select>

      {form.responseFormat === 'json_object' && (
        <TextArea
          id="outputSchema"
          labelText="Output JSON Schema"
          value={form.outputSchema || ''}
          onChange={(event) => onChange('outputSchema', event.target.value)}
          rows={8}
          placeholder={'{\n  "type": "object",\n  "properties": {\n    "summary": {"type": "string"}\n  }\n}'}
          helperText="Define the JSON schema for validation (Optional)"
          enableCounter
        />
      )}
    </Stack>
  );
}
