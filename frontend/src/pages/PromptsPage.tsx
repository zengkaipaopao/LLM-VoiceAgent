import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * PromptsPage - Prompt 管理页面
 * 
 * 用于编辑、版本对比、灰度发布智能体 Prompt
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function PromptsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:prompts.title')}
      subtitle={t('pages:prompts.subtitle')}
    >
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:prompts.emptyState')}
      />
    </PageTemplate>
  );
}
