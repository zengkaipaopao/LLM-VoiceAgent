import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * CallsPage - 通话记录页面
 * 
 * 显示所有呼入和呼出的通话记录,支持搜索和过滤
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function CallsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:calls.title')}
      subtitle={t('pages:calls.subtitle')}
    >
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:calls.emptyState')}
      />
    </PageTemplate>
  );
}
