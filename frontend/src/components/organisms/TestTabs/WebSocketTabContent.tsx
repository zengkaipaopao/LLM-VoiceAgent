import { useTranslation } from 'react-i18next';
import { Column, Grid } from '@carbon/react';

import { useLiveWebSocketConsole } from '../../../hooks/useLiveWebSocketConsole';
import { TestTabNotifications } from '../../molecules/TestTabs';
import { WebSocketMainWorkspace } from './websocket/WebSocketMainWorkspace';
import { WebSocketSidebarPanels } from './websocket/WebSocketSidebarPanels';
import styles from './WebSocketTabContent.module.scss';

export function WebSocketTabContent() {
  const { t } = useTranslation(['pages']);
  const websocket = useLiveWebSocketConsole();

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {websocket.error && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            <TestTabNotifications
              error={websocket.error}
              errorTitle={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
              successTitle={t('pages:test.unified.notifications.successTitle', 'Success')}
              onClearError={() => websocket.setError(null)}
            />
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          <WebSocketMainWorkspace
            socketStatus={websocket.socketStatus}
            micStatus={websocket.micStatus}
            loadingPrompts={websocket.loadingPrompts}
            prompts={websocket.prompts}
            selectedPromptCode={websocket.selectedPromptCode}
            setSelectedPromptCode={websocket.setSelectedPromptCode}
            model={websocket.model}
            setModel={websocket.setModel}
            modalities={websocket.modalities}
            setModalities={websocket.setModalities}
            voice={websocket.voice}
            setVoice={websocket.setVoice}
            systemInstruction={websocket.systemInstruction}
            setSystemInstruction={websocket.setSystemInstruction}
            canUseRealtimeInput={websocket.canUseRealtimeInput}
            textInput={websocket.textInput}
            setTextInput={websocket.setTextInput}
            connectSocket={websocket.connectSocket}
            disconnectSocket={websocket.disconnectSocket}
            clearConsole={websocket.clearConsole}
            sendText={websocket.sendText}
            toggleMicrophone={websocket.toggleMicrophone}
            sessionId={websocket.sessionId}
            totalTokens={websocket.totalTokens}
            displayWsUrl={websocket.displayWsUrl}
          />
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          <WebSocketSidebarPanels
            inputTranscript={websocket.inputTranscript}
            outputTranscript={websocket.outputTranscript}
            assistantText={websocket.assistantText}
            logs={websocket.logs}
          />
        </Column>
      </Grid>
    </div>
  );
}
