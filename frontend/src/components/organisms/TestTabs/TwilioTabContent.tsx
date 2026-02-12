import { useTranslation } from 'react-i18next';
import { EmptyState } from '../EmptyState';
import styles from '../../../pages/Test.module.scss';

/**
 * Twilio Tab内容组件
 * 
 * Twilio WebCall测试功能（开发中）
 */
export function TwilioTabContent() {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.tabPanelContent}>
      <EmptyState
        title={t('pages:test.tabs.twilio')}
        description={t('pages:test.twilio.description', 'Twilio WebCall测试功能开发中...')}
      />
    </div>
  );
}
