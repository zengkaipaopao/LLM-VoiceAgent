import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * SettingsPage - 系统设置页面
 * 
 * 配置语音渠道、LLM Provider 凭证以及实验性 Feature Flags
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function SettingsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:settings.title')}
      subtitle={t('pages:settings.subtitle')}
    >
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:settings.emptyState')}
      />
    </PageTemplate>
  );
}
