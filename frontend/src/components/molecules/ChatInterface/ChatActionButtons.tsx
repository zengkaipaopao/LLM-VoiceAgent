import { Button } from '@carbon/react';
import { Download, TrashCan } from '@carbon/icons-react';
import { useTranslation } from 'react-i18next';

import styles from './ChatActionButtons.module.scss';

interface ChatActionButtonsProps {
  hasMessages: boolean;
  onExport: () => void;
  onClear: () => void;
}

export function ChatActionButtons({
  hasMessages,
  onExport,
  onClear,
}: ChatActionButtonsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.actions}>
      <Button
        kind="ghost"
        size="sm"
        renderIcon={Download}
        onClick={onExport}
        disabled={!hasMessages}
      >
        {t('pages:test.chat.actions.export', 'Export')}
      </Button>
      <Button
        kind="danger--ghost"
        size="sm"
        renderIcon={TrashCan}
        onClick={onClear}
        disabled={!hasMessages}
      >
        {t('pages:test.chat.actions.clear', 'Clear')}
      </Button>
    </div>
  );
}
