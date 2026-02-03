import { InlineNotification } from '@carbon/react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * PretrainingPage - 微调页面
 * 
 * 围绕业务样本微调模型表现,减少复杂提示词成本
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function PretrainingPage() {
  return (
    <PageTemplate
      title="微调"
      subtitle="围绕业务样本微调模型表现,减少复杂提示词成本。"
    >
      <InlineNotification
        className="pretrain-notice"
        kind="info"
        lowContrast
        title="功能规划中"
        subtitle="当前提供流程指引与资源入口,后续接入训练任务与状态监控。"
      />
      <EmptyState
        title="模型微调开发中"
        description="此页面将提供模型微调的数据准备、任务创建、训练监控和模型发布功能。"
      />
    </PageTemplate>
  );
}
