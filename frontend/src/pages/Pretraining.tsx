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
        title={t('pages:pretraining.notice.title', 'Feature in planning')}
        subtitle={t(
          'pages:pretraining.notice.subtitle',
          'This page currently provides process guidance and resource links. Training jobs and status tracking will be added next.'
        )}
      />
      <EmptyState
        title={t('common:emptyState.title')}
        description={t('pages:pretraining.emptyState')}
      />
    </PageTemplate>
  );
}
