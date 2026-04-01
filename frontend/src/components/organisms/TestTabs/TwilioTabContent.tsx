import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Column, Grid } from '@carbon/react';

import { API_BASE_URL } from '../../../api/http';
import { useTwilioWebCallConsole } from '../../../hooks/useTwilioWebCallConsole';
import { TestTabNotifications } from '../../molecules/TestTabs';
import { TwilioMainWorkspace } from './twilio/TwilioMainWorkspace';
import { TwilioSidebarPanels } from './twilio/TwilioSidebarPanels';
import styles from './TwilioTabContent.module.scss';

export function TwilioTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);
  const twilio = useTwilioWebCallConsole();

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {(twilio.error || twilio.info) && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            <TestTabNotifications
              error={twilio.error}
              info={twilio.info}
              errorTitle={t('pages:test.twilio.notifications.error', 'Request failed')}
              successTitle={t('pages:test.twilio.notifications.success', 'Success')}
              onClearError={() => twilio.setError(null)}
              onClearInfo={() => twilio.setInfo(null)}
            />
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
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
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
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
        </Column>
      </Grid>
    </div>
  );
}
