import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * SettingsPage - 系统设置页面
 * 
 * 配置语音渠道、LLM Provider 凭证以及实验性 Feature Flags
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function SettingsPage() {
  return (
    <PageTemplate
      title="系统设置"
      subtitle="配置语音渠道、LLM Provider 凭证以及实验性 Feature Flags。"
    >
      <EmptyState
        title="系统设置开发中"
        description="此页面将提供智能体配置、Feature Flags 开关和系统参数设置功能。"
      />
    </PageTemplate>
  );
}
