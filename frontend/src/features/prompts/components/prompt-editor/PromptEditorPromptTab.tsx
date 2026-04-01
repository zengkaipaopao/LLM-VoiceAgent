import { Stack, TextArea } from '@carbon/react';
import { PromptFormValues } from '../../../../types/shared';

interface PromptEditorPromptTabProps {
  form: PromptFormValues;
  onChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  t: (key: string) => string;
}

export function PromptEditorPromptTab({ form, onChange, t }: PromptEditorPromptTabProps) {
  return (
    <Stack gap={6}>
      <TextArea
        id="systemPrompt"
        labelText={t('prompts.editor.fields.systemPrompt')}
        value={form.systemPrompt}
        onChange={(event) => onChange('systemPrompt', event.target.value)}
        rows={15}
        enableCounter
      />
      <TextArea
        id="extractionPrompt"
        labelText={t('prompts.editor.fields.extractionPrompt')}
        value={form.extractionPrompt || ''}
        onChange={(event) => onChange('extractionPrompt', event.target.value)}
        rows={5}
        helperText={t('prompts.editor.fields.extractionPromptHelper')}
      />
      <TextArea
        id="extractionSchema"
        labelText="Extraction JSON Schema (for table/extraction)"
        value={form.extractionSchema || ''}
        onChange={(event) => onChange('extractionSchema', event.target.value)}
        rows={8}
        placeholder={
          '{\n  "fields": [\n    {"name": "caller_name", "label": "Caller"},\n    {"name": "pickup_address", "label": "Address"}\n  ]\n}'
        }
        helperText="Define extraction fields for appointment table columns."
        enableCounter
      />
    </Stack>
  );
}
