import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useUnifiedTestLab } from '../../../hooks/useUnifiedTestLab';
import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../molecules/TestTabs';
import { UnifiedChatWorkspace } from './unified/UnifiedChatWorkspace';
import { UnifiedSidebarPanels } from './unified/UnifiedSidebarPanels';

export function UnifiedTestLabTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);
  const lab = useUnifiedTestLab();
  const canClearPanel = lab.messages.length > 0 || !!lab.error || !!lab.info;
  const sessionTone = lab.sessionClosed ? 'blue' : lab.session ? 'green' : 'cool-gray';

  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'scenario',
      label: t('pages:test.unified.summary.scenario', 'Scenario'),
      value: t('pages:test.unified.summary.scenarioValue', 'Prompt-driven call rehearsal'),
    },
    {
      id: 'prompt',
      label: t('pages:test.unified.summary.prompt', 'Prompt'),
      value: lab.selectedPromptCode || '-',
      mono: true,
    },
    {
      id: 'session',
      label: t('pages:test.unified.summary.session', 'Session'),
      value: lab.sessionStatus,
      tone: sessionTone,
    },
    {
      id: 'tokens',
      label: t('pages:test.unified.summary.tokens', 'Total Tokens'),
      value: String(lab.totalTokens),
    },
  ];

  return (
    <TestWorkbenchShell
      title={t('pages:test.unified.shell.title', 'Unified Prompt Simulation Workspace')}
      description={t(
        'pages:test.unified.shell.description',
        'Run end-to-end prompt simulations in one controlled surface, from session creation to extraction finalization.'
      )}
      summaryItems={summaryItems}
      notice={
        lab.error || lab.info ? (
          <>
            <TestTabNotifications
              error={lab.error}
              info={lab.info}
              errorTitle={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
              successTitle={t('pages:test.unified.notifications.successTitle', 'Success')}
              onClearError={() => lab.setError(null)}
              onClearInfo={() => lab.setInfo(null)}
            />
          </>
        ) : undefined
      }
      main={
        <>
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
        </>
      }
      side={
        <>
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
        </>
      }
    />
  );
}
