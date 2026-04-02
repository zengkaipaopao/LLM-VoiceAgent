import { useTranslation } from 'react-i18next';

import { useLiveWebSocketConsole } from '../../../hooks/useLiveWebSocketConsole';
import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../molecules/TestTabs';
import { WebSocketMainWorkspace } from './websocket/WebSocketMainWorkspace';
import { WebSocketSidebarPanels } from './websocket/WebSocketSidebarPanels';

export function WebSocketTabContent() {
  const { t } = useTranslation(['pages']);
  const websocket = useLiveWebSocketConsole();
  const socketTone =
    websocket.socketStatus === 'connected'
      ? 'green'
      : websocket.socketStatus === 'connecting'
        ? 'blue'
        : websocket.socketStatus === 'error'
          ? 'red'
          : 'cool-gray';
  const micTone =
    websocket.micStatus === 'on'
      ? 'green'
      : websocket.micStatus === 'starting'
        ? 'teal'
        : 'cool-gray';

  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'scenario',
      label: t('pages:test.websocket.summary.scenario', 'Scenario'),
      value: t('pages:test.websocket.summary.scenarioValue', 'Realtime gateway interaction'),
    },
    {
      id: 'socket',
      label: t('pages:test.websocket.summary.socket', 'Socket'),
      value: websocket.socketStatus,
      tone: socketTone,
    },
    {
      id: 'mic',
      label: t('pages:test.websocket.summary.mic', 'Mic'),
      value: websocket.micStatus,
      tone: micTone,
    },
    {
      id: 'prompt',
      label: t('pages:test.websocket.summary.prompt', 'Prompt'),
      value: websocket.selectedPromptCode || '-',
      mono: true,
    },
  ];

  return (
    <TestWorkbenchShell
      title={t('pages:test.websocket.shell.title', 'Gemini Live Realtime Workspace')}
      description={t(
        'pages:test.websocket.shell.description',
        'Validate websocket lifecycle, realtime text/audio flow, and prompt alignment with a consistent operator console.'
      )}
      summaryItems={summaryItems}
      notice={
        websocket.error ? (
          <>
            <TestTabNotifications
              error={websocket.error}
              errorTitle={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
              successTitle={t('pages:test.unified.notifications.successTitle', 'Success')}
              onClearError={() => websocket.setError(null)}
            />
          </>
        ) : undefined
      }
      main={
        <>
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
        </>
      }
      side={
        <>
          <WebSocketSidebarPanels
            inputTranscript={websocket.inputTranscript}
            outputTranscript={websocket.outputTranscript}
            assistantText={websocket.assistantText}
            logs={websocket.logs}
          />
        </>
      }
    />
  );
}
