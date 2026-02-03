import { PageTemplate } from '../../components/templates/PageTemplate';
import { EmptyState } from '../../components/organisms/EmptyState';

/**
 * TestHub - 实时调试实验室页面
 * 
 * 用于测试WebSocket和Twilio WebCall等链路
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function TestHub() {
  return (
    <PageTemplate
      title="实时调试实验室"
      subtitle="在单一界面体验 WebSocket 以及 Twilio WebCall 等链路,方便比对。"
    >
      <EmptyState
        title="测试功能开发中"
        description="此页面将提供WebSocket和Twilio WebCall的实时调试功能。"
      />
    </PageTemplate>
  );
}
