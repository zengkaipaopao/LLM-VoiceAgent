import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * AppointmentsPage - 预约记录页面
 * 
 * 显示自动接单助手归档的预约信息
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function AppointmentsPage() {
  return (
    <PageTemplate
      title="预约记录"
      subtitle="查看自动接单助手归档的预约信息,点击任意行以查看详细内容。"
    >
      <EmptyState
        title="预约记录开发中"
        description="此页面将显示所有预约记录,包括新建、变更和取消的预约,支持搜索和详情查看功能。"
      />
    </PageTemplate>
  );
}
