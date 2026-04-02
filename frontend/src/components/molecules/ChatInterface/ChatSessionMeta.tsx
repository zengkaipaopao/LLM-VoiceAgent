import { useTranslation } from 'react-i18next';
import styles from './ChatSessionMeta.module.scss';

interface ChatSessionMetaProps {
  callId: string | null;
  totalTokens: number;
}

export function ChatSessionMeta({ callId, totalTokens }: ChatSessionMetaProps) {
  const { t } = useTranslation(['pages']);

  if (!callId && totalTokens <= 0) {
    return null;
  }

  return (
    <div className={styles.callInfo}>
      {callId && (
        <div className={styles.infoItem}>
          <span className={styles.label}>{t('pages:test.chat.meta.callId', 'Call ID')}:</span>
          <code className={styles.callId}>{callId}</code>
        </div>
      )}
      {totalTokens > 0 && (
        <div className={styles.infoItem}>
          <span className={styles.label}>{t('pages:test.chat.meta.totalTokens', 'Total Tokens')}:</span>
          <span className={styles.tokenCount}>{totalTokens.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
