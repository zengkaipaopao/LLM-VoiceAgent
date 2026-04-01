import { useTranslation } from 'react-i18next';

import styles from '../WebSocketTabContent.module.scss';

interface WebSocketMetaListProps {
  sessionId: string;
  totalTokens: number;
  selectedPromptCode: string;
  displayWsUrl: string;
}

export function WebSocketMetaList({
  sessionId,
  totalTokens,
  selectedPromptCode,
  displayWsUrl,
}: WebSocketMetaListProps) {
  const { t } = useTranslation(['pages']);

  return (
    <dl className={styles.metaList}>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.websocket.meta.sessionId', 'Session ID')}</dt>
        <dd>{sessionId || '-'}</dd>
      </div>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.websocket.meta.tokens', 'Total Tokens')}</dt>
        <dd>{totalTokens || 0}</dd>
      </div>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.websocket.meta.prompt', 'Prompt')}</dt>
        <dd>{selectedPromptCode || '-'}</dd>
      </div>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.websocket.meta.endpoint', 'Endpoint')}</dt>
        <dd>{displayWsUrl}</dd>
      </div>
    </dl>
  );
}
