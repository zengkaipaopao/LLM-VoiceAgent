import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../../components/templates/PageTemplate';
import { EmptyState } from '../../components/organisms/EmptyState';

/**
 * TestHub - 实时调试实验室页面
 * 
 * 用于测试WebSocket和Twilio WebCall等链路
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function TestHub() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:test.title')}
      subtitle={t('pages:test.subtitle')}
    >
      <EmptyState
        title={t('pages:test.emptyState')}
        description={t('pages:test.emptyDescription')}
      />
    </PageTemplate>
  );
}
