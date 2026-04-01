import { Button } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedSessionActionButtonsProps {
  hasSession: boolean;
  sessionClosed: boolean;
  selectedPromptCode: string;
  isBusy: boolean;
  canClearPanel: boolean;
  onStartSession: () => Promise<void>;
  onFinalize: () => Promise<void>;
  onClear: () => void;
}

export function UnifiedSessionActionButtons({
  hasSession,
  sessionClosed,
  selectedPromptCode,
  isBusy,
  canClearPanel,
  onStartSession,
  onFinalize,
  onClear,
}: UnifiedSessionActionButtonsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.buttonGroup}>
      <Button
        kind="primary"
        size="sm"
        onClick={() => {
          void onStartSession();
        }}
        disabled={!selectedPromptCode || isBusy}
      >
        {hasSession
          ? t('pages:test.unified.actions.newSession', 'New Session')
          : t('pages:test.unified.actions.startSession', 'Start Session')}
      </Button>

      <Button
        kind="secondary"
        size="sm"
        onClick={() => {
          void onFinalize();
        }}
        disabled={!hasSession || isBusy || sessionClosed}
      >
        {t('pages:test.unified.actions.finalize', 'Finalize & Extract')}
      </Button>

      <Button kind="ghost" size="sm" onClick={onClear} disabled={!canClearPanel}>
        {t('pages:test.unified.actions.clearPanel', 'Clear Panel')}
      </Button>
    </div>
  );
}
