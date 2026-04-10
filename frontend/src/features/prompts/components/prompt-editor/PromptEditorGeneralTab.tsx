import { Checkbox, Select, SelectItem, Stack, TextArea, TextInput } from '@carbon/react';
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
      <TextArea
        id="twilio_inbound_numbers"
        labelText="Twilio 入呼号码"
        value={form.twilioInboundNumbers || ''}
        onChange={(event) => onChange('twilioInboundNumbers', event.target.value)}
        helperText="一行一个 E.164 号码，或用逗号分隔。真实电话直接打入这些号码时，会路由到当前 Agent。"
        rows={4}
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
      <Checkbox
        id="is_twilio_incoming_default"
        labelText="设为 Twilio 入呼回退 Agent"
        checked={Boolean(form.isTwilioIncomingDefault)}
        onChange={(_, { checked }) => onChange('isTwilioIncomingDefault', Boolean(checked))}
      />
      <p style={{ marginTop: '-0.5rem', color: 'var(--cds-text-secondary)' }}>
        当来电号码没有命中上面的号码绑定，且没有测试页临时覆盖时，才会回退到这个 Agent。
      </p>
    </Stack>
  );
}
