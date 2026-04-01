import { Select, SelectItem, TextArea, TextInput } from '@carbon/react';
import { useTranslation } from 'react-i18next';

interface WebSocketRealtimeConfigFieldsProps {
  model: string;
  setModel: (value: string) => void;
  modalities: string;
  setModalities: (value: string) => void;
  voice: string;
  setVoice: (value: string) => void;
  selectedPromptCode: string;
  systemInstruction: string;
  setSystemInstruction: (value: string) => void;
  disabled: boolean;
}

export function WebSocketRealtimeConfigFields({
  model,
  setModel,
  modalities,
  setModalities,
  voice,
  setVoice,
  selectedPromptCode,
  systemInstruction,
  setSystemInstruction,
  disabled,
}: WebSocketRealtimeConfigFieldsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <>
      <TextInput
        id="live-model"
        labelText={t('pages:test.websocket.form.model', 'Model')}
        value={model}
        onChange={(event) => setModel(event.target.value)}
        disabled={disabled}
      />

      <Select
        id="live-modalities"
        labelText={t('pages:test.websocket.form.modalities', 'Response Modalities')}
        value={modalities}
        onChange={(event) => setModalities(event.target.value)}
        disabled={disabled}
      >
        <SelectItem value="AUDIO" text="AUDIO" />
        <SelectItem value="TEXT" text="TEXT" />
        <SelectItem value="AUDIO,TEXT" text="AUDIO + TEXT" />
      </Select>

      <TextInput
        id="live-voice"
        labelText={t('pages:test.websocket.form.voice', 'Voice (optional)')}
        value={voice}
        onChange={(event) => setVoice(event.target.value)}
        disabled={disabled}
        placeholder="Aoede"
      />

      {!selectedPromptCode && (
        <TextArea
          id="live-system-instruction"
          labelText={t('pages:test.websocket.form.systemInstruction', 'System Instruction')}
          value={systemInstruction}
          rows={3}
          onChange={(event) => setSystemInstruction(event.target.value)}
          disabled={disabled}
        />
      )}
    </>
  );
}
