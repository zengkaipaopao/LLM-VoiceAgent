import { InlineNotification } from '@carbon/react';
import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * PretrainingPage - 微调页面
 * 
 * 围绕业务样本微调模型表现,减少复杂提示词成本
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function Pretraining() {
  const { t } = useTranslation(['pages', 'common']);
  
  return (
    <PageTemplate
      title={t('pages:pretraining.title')}
      subtitle={t('pages:pretraining.subtitle')}
    >
      <InlineNotification
        className="pretrain-notice"
        kind="info"
        lowContrast
        title="功能规划中"
        subtitle="当前提供流程指引与资源入口,后续接入训练任务与状态监控。"
      />
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:pretraining.emptyState')}
      />
    </PageTemplate>
  );
}
