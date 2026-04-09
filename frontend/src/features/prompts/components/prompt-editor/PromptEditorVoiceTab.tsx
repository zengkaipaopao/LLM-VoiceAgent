import { Select, SelectItem, Stack, TextInput } from '@carbon/react';
import { PromptFormValues } from '../../../../types/shared';

interface PromptEditorVoiceTabProps {
  form: PromptFormValues;
  geminiVoices: string[];
  loadingGeminiVoices: boolean;
  geminiVoiceLoadError: string | null;
  onChange: <K extends keyof PromptFormValues>(field: K, value: PromptFormValues[K]) => void;
  t: (key: string) => string;
}

export function PromptEditorVoiceTab({
  form,
  geminiVoices,
  loadingGeminiVoices,
  geminiVoiceLoadError,
  onChange,
  t,
}: PromptEditorVoiceTabProps) {
  const isGeminiVoice = (form.voiceProvider || '').trim() === 'gemini';

  return (
    <Stack gap={6}>
      <Select
        id="voiceProvider"
        labelText={t('prompts.editor.fields.voiceProvider')}
        value={form.voiceProvider || ''}
        onChange={(event) => {
          const nextProvider = event.target.value;
          onChange('voiceProvider', nextProvider);
          if (!nextProvider) {
            onChange('voiceId', '');
          }
        }}
      >
        <SelectItem value="" text="None (Text only)" />
        <SelectItem value="gemini" text="Google Gemini" />
        <SelectItem value="elevenlabs" text="ElevenLabs" />
        <SelectItem value="openai" text="OpenAI TTS" />
        <SelectItem value="system" text="System TTS" />
      </Select>
      {isGeminiVoice ? (
        <Select
          id="voiceId"
          labelText={t('prompts.editor.fields.voiceId')}
          value={form.voiceId || ''}
          onChange={(event) => onChange('voiceId', event.target.value)}
          helperText={
            geminiVoiceLoadError
              ? `Gemini 音色列表加载失败，当前使用静态列表。${geminiVoiceLoadError}`
              : '选择 Prompt 的默认 Gemini 音色；语音测试页留空时会默认跟随这里。'
          }
          disabled={loadingGeminiVoices}
        >
          <SelectItem
            value=""
            text={loadingGeminiVoices ? 'Loading Gemini voices...' : '请选择默认 Gemini 音色'}
          />
          {geminiVoices.map((voice) => (
            <SelectItem key={voice} value={voice} text={voice} />
          ))}
          {!geminiVoices.includes(form.voiceId || '') && form.voiceId ? (
            <SelectItem value={form.voiceId} text={`${form.voiceId} (Current)`} />
          ) : null}
        </Select>
      ) : (
        <TextInput
          id="voiceId"
          labelText={t('prompts.editor.fields.voiceId')}
          value={form.voiceId || ''}
          onChange={(event) => onChange('voiceId', event.target.value)}
          disabled={!form.voiceProvider}
        />
      )}
    </Stack>
  );
}
