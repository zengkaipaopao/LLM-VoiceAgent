import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * DashboardPage - 仪表盘页面
 * 
 * 显示系统概览信息,包括呼叫量、成功率和智能体状态
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function DashboardPage() {
  return (
    <PageTemplate
      title="仪表盘"
      subtitle="概览当前的呼叫量、成功率和正在运行的智能体。"
    >
      <EmptyState
        title="仪表盘开发中"
        description="此页面将显示系统统计数据、呼叫趋势图表和智能体运行状态。"
      />
    </PageTemplate>
  );
}
