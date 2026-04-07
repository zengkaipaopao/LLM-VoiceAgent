import { Stack, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  voiceOnlyMode: boolean;
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
  voiceOnlyMode,
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
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.mainTile}>
      <WebSocketStatusHeader
        socketStatus={socketStatus}
        micStatus={micStatus}
        voiceOnlyMode={voiceOnlyMode}
      />

      <Stack gap={6}>
        <section className={styles.sectionBlock}>
          <h4 className="cds--heading-01">{t('pages:test.websocket.sections.setup', 'Session Setup')}</h4>
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
            voiceOnlyMode={voiceOnlyMode}
          />
          {voiceOnlyMode && (
            <p className={styles.helperText}>
              {t(
                'pages:test.websocket.sections.setupHint',
                'Voice-only mode uses prompt templates only. Manual instruction input is hidden.'
              )}
            </p>
          )}
        </section>

        <section className={styles.sectionBlock}>
          <h4 className="cds--heading-01">
            {t('pages:test.websocket.sections.realtimeControls', 'Realtime Controls')}
          </h4>
          <WebSocketControls
            socketStatus={socketStatus}
            micStatus={micStatus}
            canUseRealtimeInput={canUseRealtimeInput}
            voiceOnlyMode={voiceOnlyMode}
            textInput={textInput}
            setTextInput={setTextInput}
            connectSocket={connectSocket}
            disconnectSocket={disconnectSocket}
            clearConsole={clearConsole}
            sendText={sendText}
            toggleMicrophone={toggleMicrophone}
          />
        </section>

        <section className={styles.sectionBlock}>
          <h4 className="cds--heading-01">
            {t('pages:test.websocket.sections.sessionMetadata', 'Session Metadata')}
          </h4>
          <WebSocketMetaList
            sessionId={sessionId}
            totalTokens={totalTokens}
            selectedPromptCode={selectedPromptCode}
            displayWsUrl={displayWsUrl}
          />
        </section>
      </Stack>
    </Tile>
  );
}
