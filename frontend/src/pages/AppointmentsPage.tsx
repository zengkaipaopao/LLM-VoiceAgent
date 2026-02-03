import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * AppointmentsPage - 预约记录页面
 * 
 * 显示自动接单助手归档的预约信息
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function AppointmentsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:appointments.title')}
      subtitle={t('pages:appointments.subtitle')}
    >
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:appointments.emptyState')}
      />
    </PageTemplate>
  );
}
