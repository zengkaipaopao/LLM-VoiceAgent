import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * DashboardPage - 仪表盘页面
 * 
 * 显示系统概览信息,包括呼叫量、成功率和智能体状态
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function DashboardPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:dashboard.title')}
      subtitle={t('pages:dashboard.subtitle')}
    >
      <EmptyState 
        title={t('common:emptyState.title')}
        description={t('pages:dashboard.emptyState')}
      />
    </PageTemplate>
  );
}
