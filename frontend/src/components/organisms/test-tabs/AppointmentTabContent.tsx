import { useTranslation } from 'react-i18next';
import { EmptyState } from '../EmptyState';
import styles from '../../../pages/TestPage.module.css';

/**
 * Appointment Tab内容组件
 * 
 * 预约模拟测试功能（开发中）
 */
export function AppointmentTabContent() {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.tabPanelContent}>
      <EmptyState
        title={t('pages:test.tabs.appointment')}
        description={t('pages:test.appointment.description', '预约模拟测试功能开发中...')}
      />
    </div>
  );
}
