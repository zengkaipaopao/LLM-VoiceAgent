import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * PromptsPage - Prompt 管理页面
 * 
 * 用于编辑、版本对比、灰度发布智能体 Prompt
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function PromptsPage() {
  return (
    <PageTemplate
      title="Prompt 管理"
      subtitle="编辑、版本对比、灰度发布智能体 Prompt 的公共入口。"
    >
      <EmptyState
        title="Prompt 管理开发中"
        description="此页面将提供 Prompt 模板的创建、编辑、版本管理和模型配置功能。"
      />
    </PageTemplate>
  );
}
