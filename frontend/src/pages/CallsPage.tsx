import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';

/**
 * CallsPage - 通话记录页面
 * 
 * 显示所有呼入和呼出的通话记录,支持搜索和过滤
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function CallsPage() {
  return (
    <PageTemplate
      title="通话记录"
      subtitle="查看每一次呼入或呼出的细节,并准备接入录音、搜索与过滤。"
    >
      <EmptyState
        title="通话记录开发中"
        description="此页面将显示通话历史记录,包括通话时长、状态、对端号码等信息,并支持搜索和导出功能。"
      />
    </PageTemplate>
  );
}
