import { Select, SelectItem, Stack, TextInput } from '@carbon/react';
import { PromptFormValues } from '../../../../types/shared';

interface PromptEditorGeneralTabProps {
  form: PromptFormValues;
  isEditMode: boolean;
  onChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  t: (key: string) => string;
}

export function PromptEditorGeneralTab({
  form,
  isEditMode,
  onChange,
  t,
}: PromptEditorGeneralTabProps) {
  return (
    <Stack gap={6}>
      <TextInput
        id="name"
        labelText={t('prompts.editor.fields.name')}
        value={form.name}
        onChange={(event) => onChange('name', event.target.value)}
        placeholder={t('prompts.editor.fields.namePlaceholder')}
      />
      <TextInput
        id="code"
        labelText={t('prompts.editor.fields.code')}
        value={form.code}
        onChange={(event) => onChange('code', event.target.value)}
        placeholder={t('prompts.editor.fields.codePlaceholder')}
        readOnly={isEditMode}
        helperText={isEditMode ? 'Code cannot be changed' : 'Unique identifier for this agent'}
      />
      <TextInput
        id="description"
        labelText={t('prompts.editor.fields.description')}
        value={form.description || ''}
        onChange={(event) => onChange('description', event.target.value)}
      />
      <Select
        id="category"
        labelText="Category"
        value={form.category || 'booking'}
        onChange={(event) => onChange('category', event.target.value)}
      >
        <SelectItem value="booking" text="Booking" />
        <SelectItem value="customer_service" text="Customer Service" />
        <SelectItem value="support" text="Support" />
        <SelectItem value="sales" text="Sales" />
        <SelectItem value="other" text="Other" />
      </Select>
    </Stack>
  );
}
