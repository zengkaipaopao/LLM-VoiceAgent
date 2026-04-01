import { Stack, Tile } from '@carbon/react';

import {
  MicStatus,
  SocketStatus,
} from '../../../../hooks/useLiveWebSocketConsole';
import { PromptTemplate } from '../../../../types/shared';
import { WebSocketConfigForm } from './WebSocketConfigForm';
import { WebSocketControls } from './WebSocketControls';
import { WebSocketMetaList } from './WebSocketMetaList';
import { WebSocketStatusHeader } from './WebSocketStatusHeader';
import styles from '../WebSocketTabContent.module.scss';

interface WebSocketMainWorkspaceProps {
  socketStatus: SocketStatus;
  micStatus: MicStatus;
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
  canUseRealtimeInput: boolean;
  textInput: string;
  setTextInput: (value: string) => void;
  connectSocket: () => void;
  disconnectSocket: () => void;
  clearConsole: () => void;
  sendText: () => void;
  toggleMicrophone: (enabled: boolean) => void;
  sessionId: string;
  totalTokens: number;
  displayWsUrl: string;
}

export function WebSocketMainWorkspace({
  socketStatus,
  micStatus,
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
  canUseRealtimeInput,
  textInput,
  setTextInput,
  connectSocket,
  disconnectSocket,
  clearConsole,
  sendText,
  toggleMicrophone,
  sessionId,
  totalTokens,
  displayWsUrl,
}: WebSocketMainWorkspaceProps) {
  return (
    <Tile className={styles.mainTile}>
      <WebSocketStatusHeader socketStatus={socketStatus} micStatus={micStatus} />

      <Stack gap={6}>
        <WebSocketConfigForm
          loadingPrompts={loadingPrompts}
          prompts={prompts}
          selectedPromptCode={selectedPromptCode}
          setSelectedPromptCode={setSelectedPromptCode}
          model={model}
          setModel={setModel}
          modalities={modalities}
          setModalities={setModalities}
          voice={voice}
          setVoice={setVoice}
          systemInstruction={systemInstruction}
          setSystemInstruction={setSystemInstruction}
          socketStatus={socketStatus}
        />

        <WebSocketControls
          socketStatus={socketStatus}
          micStatus={micStatus}
          canUseRealtimeInput={canUseRealtimeInput}
          textInput={textInput}
          setTextInput={setTextInput}
          connectSocket={connectSocket}
          disconnectSocket={disconnectSocket}
          clearConsole={clearConsole}
          sendText={sendText}
          toggleMicrophone={toggleMicrophone}
        />

        <WebSocketMetaList
          sessionId={sessionId}
          totalTokens={totalTokens}
          selectedPromptCode={selectedPromptCode}
          displayWsUrl={displayWsUrl}
        />
      </Stack>
    </Tile>
  );
}
