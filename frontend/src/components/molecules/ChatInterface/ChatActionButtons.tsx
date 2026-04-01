import { Button } from '@carbon/react';
import { Download, TrashCan } from '@carbon/icons-react';

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
  return (
    <div className={styles.actions}>
      <Button
        kind="ghost"
        size="sm"
        renderIcon={Download}
        onClick={onExport}
        disabled={!hasMessages}
      >
        导出
      </Button>
      <Button
        kind="danger--ghost"
        size="sm"
        renderIcon={TrashCan}
        onClick={onClear}
        disabled={!hasMessages}
      >
        清空
      </Button>
    </div>
  );
}
