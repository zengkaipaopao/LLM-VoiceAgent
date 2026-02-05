import { useTranslation } from 'react-i18next';
import { EmptyState } from '../EmptyState';
import styles from '../../../pages/TestPage.module.scss';

/**
 * WebSocket Tab内容组件
 * 
 * WebSocket测试功能（开发中）
 */
export function WebSocketTabContent() {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.tabPanelContent}>
      <EmptyState
        title={t('pages:test.tabs.websocket')}
        description={t('pages:test.websocket.description', 'WebSocket测试功能开发中...')}
      />
    </div>
  );
}
