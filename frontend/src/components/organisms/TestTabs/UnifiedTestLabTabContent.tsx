import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Column, Grid } from '@carbon/react';

import { useUnifiedTestLab } from '../../../hooks/useUnifiedTestLab';
import { TestTabNotifications } from '../../molecules/TestTabs';
import { UnifiedChatWorkspace } from './unified/UnifiedChatWorkspace';
import { UnifiedSidebarPanels } from './unified/UnifiedSidebarPanels';
import styles from './UnifiedTestLabTabContent.module.scss';

export function UnifiedTestLabTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);
  const lab = useUnifiedTestLab();
  const canClearPanel = lab.messages.length > 0 || !!lab.error || !!lab.info;

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {(lab.error || lab.info) && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            <TestTabNotifications
              error={lab.error}
              info={lab.info}
              errorTitle={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
              successTitle={t('pages:test.unified.notifications.successTitle', 'Success')}
              onClearError={() => lab.setError(null)}
              onClearInfo={() => lab.setInfo(null)}
            />
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          <UnifiedChatWorkspace
            hasSession={!!lab.session}
            sessionClosed={lab.sessionClosed}
            sessionStatus={lab.sessionStatus}
            messages={lab.messages}
            isSending={lab.isSending}
            selectedPromptCode={lab.selectedPromptCode}
            isStarting={lab.isStarting}
            isFinalizing={lab.isFinalizing}
            quickMessages={lab.quickMessages}
            onSendMessage={lab.handleSendMessage}
          />
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          <UnifiedSidebarPanels
            loadingPrompts={lab.loadingPrompts}
            prompts={lab.prompts}
            selectedPromptCode={lab.selectedPromptCode}
            setSelectedPromptCode={lab.setSelectedPromptCode}
            callerName={lab.callerName}
            setCallerName={lab.setCallerName}
            hasSession={!!lab.session}
            sessionClosed={lab.sessionClosed}
            isStarting={lab.isStarting}
            isSending={lab.isSending}
            isFinalizing={lab.isFinalizing}
            canClearPanel={canClearPanel}
            onStartSession={lab.handleStartSession}
            onFinalize={lab.handleFinalize}
            onClear={lab.handleClear}
            selectedPrompt={lab.selectedPrompt}
            session={lab.session}
            totalTokens={lab.totalTokens}
            finalizeResult={lab.finalizeResult}
            onViewCalls={() => navigate('/calls')}
            onViewAppointments={() => navigate('/appointments')}
          />
        </Column>
      </Grid>
    </div>
  );
}
