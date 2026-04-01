import { PromptTemplate } from '../../../../types/shared';
import { SocketStatus } from '../../../../hooks/useLiveWebSocketConsole';
import { WebSocketPromptTemplateSelect } from './WebSocketPromptTemplateSelect';
import { WebSocketRealtimeConfigFields } from './WebSocketRealtimeConfigFields';
import styles from '../WebSocketTabContent.module.scss';

interface WebSocketConfigFormProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  model: string;
  setModel: (value: string) => void;
  modalities: string;
  setModalities: (value: string) => void;
  voice: string;
  setVoice: (value: string) => void;
  systemInstruction: string;
  setSystemInstruction: (value: string) => void;
  socketStatus: SocketStatus;
}

export function WebSocketConfigForm({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  model,
  setModel,
  modalities,
  setModalities,
  voice,
  setVoice,
  systemInstruction,
  setSystemInstruction,
  socketStatus,
}: WebSocketConfigFormProps) {
  const disableInputs = socketStatus === 'connected' || socketStatus === 'connecting';

  return (
    <div className={styles.formGrid}>
      <WebSocketPromptTemplateSelect
        loadingPrompts={loadingPrompts}
        prompts={prompts}
        selectedPromptCode={selectedPromptCode}
        setSelectedPromptCode={setSelectedPromptCode}
        disabled={disableInputs}
      />

      <WebSocketRealtimeConfigFields
        model={model}
        setModel={setModel}
        modalities={modalities}
        setModalities={setModalities}
        voice={voice}
        setVoice={setVoice}
        selectedPromptCode={selectedPromptCode}
        systemInstruction={systemInstruction}
        setSystemInstruction={setSystemInstruction}
        disabled={disableInputs}
      />
    </div>
  );
}
