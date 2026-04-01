import { Select, SelectItem, Stack, TextInput } from '@carbon/react';
import { PromptFormValues } from '../../../../types/shared';

interface PromptEditorVoiceTabProps {
  form: PromptFormValues;
  onChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  t: (key: string) => string;
}

export function PromptEditorVoiceTab({ form, onChange, t }: PromptEditorVoiceTabProps) {
  return (
    <Stack gap={6}>
      <Select
        id="voiceProvider"
        labelText={t('prompts.editor.fields.voiceProvider')}
        value={form.voiceProvider || ''}
        onChange={(event) => onChange('voiceProvider', event.target.value)}
      >
        <SelectItem value="" text="None (Text only)" />
        <SelectItem value="elevenlabs" text="ElevenLabs" />
        <SelectItem value="openai" text="OpenAI TTS" />
        <SelectItem value="system" text="System TTS" />
      </Select>
      <TextInput
        id="voiceId"
        labelText={t('prompts.editor.fields.voiceId')}
        value={form.voiceId || ''}
        onChange={(event) => onChange('voiceId', event.target.value)}
        disabled={!form.voiceProvider}
      />
    </Stack>
  );
}
