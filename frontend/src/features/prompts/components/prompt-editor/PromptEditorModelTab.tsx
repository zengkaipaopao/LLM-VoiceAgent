import { NumberInput, Select, SelectItem, Stack, TextArea } from '@carbon/react';
import { PromptFormValues } from '../../../../types/shared';

interface PromptEditorModelTabProps {
  form: PromptFormValues;
  models: string[];
  loadingModels: boolean;
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
        helperText="Select a model supported by the provider"
        disabled={loadingModels}
      >
        {models.map((model) => (
          <SelectItem key={model} value={model} text={model} />
        ))}
        {!models.includes(form.llmModel) && form.llmModel && (
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
