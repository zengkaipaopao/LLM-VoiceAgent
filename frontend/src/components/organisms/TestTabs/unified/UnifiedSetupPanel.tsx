import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { UnifiedPromptCallerFields } from './UnifiedPromptCallerFields';
import { UnifiedSessionActionButtons } from './UnifiedSessionActionButtons';
import { PromptTemplate } from '../../../../types/shared';
import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedSetupPanelProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  callerName: string;
  setCallerName: (value: string) => void;
  hasSession: boolean;
  sessionClosed: boolean;
  isStarting: boolean;
  isSending: boolean;
  isFinalizing: boolean;
  canClearPanel: boolean;
  onStartSession: () => Promise<void>;
  onFinalize: () => Promise<void>;
  onClear: () => Promise<void>;
}

export function UnifiedSetupPanel({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  callerName,
  setCallerName,
  hasSession,
  sessionClosed,
  isStarting,
  isSending,
  isFinalizing,
  canClearPanel,
  onStartSession,
  onFinalize,
  onClear,
}: UnifiedSetupPanelProps) {
  const { t } = useTranslation(['pages']);
  const isBusy = isStarting || isSending || isFinalizing;

  return (
    <Tile className={styles.panelTile}>
      <div>
        <h4 className="cds--heading-01">{t('pages:test.unified.sections.setupTitle', 'Session Setup')}</h4>
        <p className={styles.sectionDescription}>
          {t(
            'pages:test.unified.sections.setupDescription',
            'Choose a prompt and create a simulation session before or during chat.'
          )}
        </p>
      </div>

      <UnifiedPromptCallerFields
        loadingPrompts={loadingPrompts}
        prompts={prompts}
        selectedPromptCode={selectedPromptCode}
        setSelectedPromptCode={setSelectedPromptCode}
        callerName={callerName}
        setCallerName={setCallerName}
        disabled={isBusy}
      />

      <UnifiedSessionActionButtons
        hasSession={hasSession}
        sessionClosed={sessionClosed}
        selectedPromptCode={selectedPromptCode}
        isBusy={isBusy}
        canClearPanel={canClearPanel}
        onStartSession={onStartSession}
        onFinalize={onFinalize}
        onClear={onClear}
      />
    </Tile>
  );
}
