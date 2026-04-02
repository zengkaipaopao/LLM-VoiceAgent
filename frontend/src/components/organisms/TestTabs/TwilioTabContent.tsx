import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { API_BASE_URL } from '../../../api/http';
import { useTwilioWebCallConsole } from '../../../hooks/useTwilioWebCallConsole';
import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../molecules/TestTabs';
import { TwilioMainWorkspace } from './twilio/TwilioMainWorkspace';
import { TwilioSidebarPanels } from './twilio/TwilioSidebarPanels';

export function TwilioTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);
  const twilio = useTwilioWebCallConsole();
  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'scenario',
      label: t('pages:test.twilio.summary.scenario', 'Scenario'),
      value: t('pages:test.twilio.summary.scenarioValue', 'Browser-to-PSTN workflow rehearsal'),
    },
    {
      id: 'device',
      label: t('pages:test.twilio.summary.device', 'Device'),
      value: twilio.deviceState,
      tone: twilio.deviceTagType,
    },
    {
      id: 'call',
      label: t('pages:test.twilio.summary.call', 'Call'),
      value: twilio.callState,
      tone: twilio.callTagType,
    },
    {
      id: 'prompt',
      label: t('pages:test.twilio.summary.prompt', 'Prompt'),
      value: twilio.selectedPromptCode || '-',
      mono: true,
    },
  ];

  return (
    <TestWorkbenchShell
      title={t('pages:test.twilio.shell.title', 'Twilio WebCall Workspace')}
      description={t(
        'pages:test.twilio.shell.description',
        'Operate token, registration, dialing, and prompt routing from a unified telephony test control plane.'
      )}
      summaryItems={summaryItems}
      notice={
        twilio.error || twilio.info ? (
          <>
            <TestTabNotifications
              error={twilio.error}
              info={twilio.info}
              errorTitle={t('pages:test.twilio.notifications.error', 'Request failed')}
              successTitle={t('pages:test.twilio.notifications.success', 'Success')}
              onClearError={() => twilio.setError(null)}
              onClearInfo={() => twilio.setInfo(null)}
            />
          </>
        ) : undefined
      }
      main={
        <>
          <TwilioMainWorkspace
            deviceState={twilio.deviceState}
            callState={twilio.callState}
            deviceTagType={twilio.deviceTagType}
            callTagType={twilio.callTagType}
            identity={twilio.identity}
            setIdentity={twilio.setIdentity}
            toNumber={twilio.toNumber}
            setToNumber={twilio.setToNumber}
            loadingPrompts={twilio.loadingPrompts}
            prompts={twilio.prompts}
            selectedPromptCode={twilio.selectedPromptCode}
            setSelectedPromptCode={twilio.setSelectedPromptCode}
            isDialing={twilio.isDialing}
            isEnding={twilio.isEnding}
            canHangup={twilio.canHangup}
            canMute={twilio.canMute}
            isMuted={twilio.isMuted}
            handleDial={twilio.handleDial}
            handleHangUp={twilio.handleHangUp}
            handleToggleMute={twilio.handleToggleMute}
            clearLogs={twilio.clearLogs}
            callSid={twilio.callSid}
            activePrompt={twilio.activePrompt}
            useEndpoint={twilio.useEndpoint}
            tokenEndpoint={twilio.tokenEndpoint}
            logs={twilio.logs}
          />
        </>
      }
      side={
        <>
          <TwilioSidebarPanels
            useEndpoint={twilio.useEndpoint}
            setUseEndpoint={twilio.setUseEndpoint}
            tokenEndpoint={twilio.tokenEndpoint}
            setTokenEndpoint={twilio.setTokenEndpoint}
            accessToken={twilio.accessToken}
            setAccessToken={twilio.setAccessToken}
            tokenEndpointPlaceholder={`${API_BASE_URL}/twilio/token`}
            isFetchingToken={twilio.isFetchingToken}
            isInitializing={twilio.isInitializing}
            fetchToken={twilio.fetchToken}
            initializeDevice={twilio.initializeDevice}
            handleUnregister={twilio.handleUnregister}
            resetSession={twilio.resetSession}
            onViewCalls={() => {
              navigate('/calls');
            }}
          />
        </>
      }
    />
  );
}
