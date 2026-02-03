import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  TableToolbarMenu,
  TableBatchActions,
  TableBatchAction,
  Pagination,
  Tag,
  Loading,
  Button,
  OverflowMenu,
  OverflowMenuItem,
  Modal,
} from '@carbon/react';
import {
  PhoneIncoming,
  PhoneOutgoing,
  View,
  Bot,
  User,
  ArrowsHorizontal,
  Filter,
} from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';

interface Call {
  id: string;
  direction: 'inbound' | 'outbound';
  counterpart: string;
  caller_name?: string;
  started_at: string;
  answered_at?: string;
  ended_at?: string;
  duration_seconds: number;
  status: string;
  handler_type?: string;
  is_answered: boolean;
  ai_confidence?: number;
  summary?: string;
  transcript?: string;
  created_at: string;
}

interface CallsResponse {
  success: boolean;
  data: {
    items: Call[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

export function CallsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  // State
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [handlerFilter, setHandlerFilter] = useState('');
  const [sortBy, setSortBy] = useState('started_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  // Fetch calls
  const fetchCalls = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        order: sortOrder,
      });

      if (searchQuery) params.append('search', searchQuery);
      if (statusFilter) params.append('status', statusFilter);
      if (handlerFilter) params.append('handler_type', handlerFilter);

      const response = await fetch(`/api/v1/calls?${params}`);
      const data: CallsResponse = await response.json();

      if (data.success) {
        setCalls(data.data.items);
        setTotal(data.data.total);
      }
    } catch (error) {
      console.error('Failed to fetch calls:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, [page, pageSize, searchQuery, statusFilter, handlerFilter, sortBy, sortOrder]);

  // Format duration
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Format date with year
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Format call ID (show first 8 characters)
  const formatCallId = (id: string): string => {
    return id.substring(0, 8);
  };

  // Get status tag
  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { type: any; label: string }> = {
      completed: { type: 'green', label: '已完成' },
      ongoing: { type: 'blue', label: '进行中' },
      failed: { type: 'red', label: '失败' },
      no_answer: { type: 'gray', label: '未接听' },
      ringing: { type: 'cyan', label: '响铃中' },
      busy: { type: 'magenta', label: '忙线' },
    };

    const config = statusMap[status] || { type: 'gray', label: status };
    return <Tag type={config.type} size="sm">{config.label}</Tag>;
  };

  // Get handler display
  const getHandlerDisplay = (handlerType?: string) => {
    const handlerMap: Record<string, { icon: any; label: string }> = {
      ai: { icon: Bot, label: 'AI' },
      human: { icon: User, label: '人工' },
      transferred: { icon: ArrowsHorizontal, label: '转接' },
    };

    if (!handlerType) return '-';
    
    const config = handlerMap[handlerType];
    if (!config) return handlerType;

    const Icon = config.icon;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Icon size={16} />
        <span>{config.label}</span>
      </div>
    );
  };

  // Table headers
  const headers = [
    { key: 'call_id', header: '通话ID' },
    { key: 'caller', header: '来电者' },
    { key: 'status', header: '状态' },
    { key: 'handler', header: '处理' },
    { key: 'started_at', header: '时间' },
    { key: 'duration', header: '时长' },
    { key: 'confidence', header: 'AI置信度' },  // 保留此列,如果你想删除,告诉我
    { key: 'actions', header: '' },
  ];

  // Table rows
  const rows = calls.map((call) => ({
    id: call.id,
    direction: call.direction,
    caller: call.caller_name || call.counterpart,
    counterpart: call.counterpart,
    status: call.status,
    handler: call.handler_type,
    started_at: call.started_at,
    duration: call.duration_seconds,
    confidence: call.ai_confidence,
  }));

  return (
    <PageTemplate
      title="通话记录"
      subtitle="查看和管理所有通话记录"
    >
      <div style={{ backgroundColor: 'var(--cds-layer-00)', padding: '1rem' }}>
        <DataTable rows={rows} headers={headers} isSortable>
          {({
            rows,
            headers,
            getHeaderProps,
            getRowProps,
            getTableProps,
            getToolbarProps,
            onInputChange,
            getTableContainerProps,
          }) => (
            <TableContainer
              {...getTableContainerProps()}
              style={{ backgroundColor: 'var(--cds-layer-01)' }}
            >
              <TableToolbar {...getToolbarProps()}>
                <TableToolbarContent>
                  {/* 搜索框 - 默认收起 */}
                  <TableToolbarSearch
                    persistent={false}
                    placeholder="搜索来电者或号码"
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                      setSearchQuery(e.target.value);
                      setPage(1); // Reset to first page on search
                    }}
                    onClear={() => {
                      setSearchQuery('');
                      setPage(1);
                    }}
                  />
                  
                  {/* 筛选菜单 */}
                  <TableToolbarMenu
                    renderIcon={Filter}
                    iconDescription="筛选"
                  >
                    <OverflowMenuItem
                      itemText="全部状态"
                      onClick={() => setStatusFilter('')}
                    />
                    <OverflowMenuItem
                      itemText="已完成"
                      onClick={() => setStatusFilter('completed')}
                    />
                    <OverflowMenuItem
                      itemText="进行中"
                      onClick={() => setStatusFilter('ongoing')}
                    />
                    <OverflowMenuItem
                      itemText="失败"
                      onClick={() => setStatusFilter('failed')}
                    />
                    <OverflowMenuItem
                      itemText="未接听"
                      onClick={() => setStatusFilter('no_answer')}
                    />
                  </TableToolbarMenu>
                </TableToolbarContent>
              </TableToolbar>

              {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center' }}>
                  <Loading description="加载中..." withOverlay={false} />
                </div>
              ) : (
                <>
                  <Table {...getTableProps()} size="lg">
                    <TableHead>
                      <TableRow>
                        {headers.map((header) => (
                          <TableHeader
                            {...getHeaderProps({ header })}
                            key={header.key}
                            isSortable={header.key !== 'actions'}
                          >
                            {header.header}
                          </TableHeader>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rows.map((row) => {
                        const call = calls.find((c) => c.id === row.id);
                        if (!call) return null;

                        return (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            <TableCell>
                              <code style={{ 
                                fontSize: '0.75rem',
                                backgroundColor: 'var(--cds-layer-02)',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontFamily: 'monospace'
                              }}>
                                {formatCallId(call.id)}
                              </code>
                            </TableCell>
                            <TableCell>
                              <div>
                                <div style={{ fontWeight: 500 }}>
                                  {call.caller_name || '未知'}
                                </div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--cds-text-secondary)' }}>
                                  {call.counterpart}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>{getStatusTag(call.status)}</TableCell>
                            <TableCell>{getHandlerDisplay(call.handler_type)}</TableCell>
                            <TableCell>{formatDate(call.started_at)}</TableCell>
                            <TableCell>{formatDuration(call.duration_seconds)}</TableCell>
                            <TableCell>
                              {call.ai_confidence !== null && call.ai_confidence !== undefined
                                ? `${call.ai_confidence}%`
                                : '-'}
                            </TableCell>
                            <TableCell>
                              <Button
                                kind="ghost"
                                size="sm"
                                renderIcon={View}
                                iconDescription="查看详情"
                                hasIconOnly
                                onClick={() => {
                                  setSelectedCall(call);
                                  setDetailModalOpen(true);
                                }}
                              />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>

                  <Pagination
                    page={page}
                    pageSize={pageSize}
                    pageSizes={[10, 20, 50, 100]}
                    totalItems={total}
                    onChange={({ page, pageSize }) => {
                      setPage(page);
                      setPageSize(pageSize);
                    }}
                  />
                </>
              )}
            </TableContainer>
          )}
        </DataTable>
      </div>

      {/* 详情Modal */}
      <Modal
        open={detailModalOpen}
        onRequestClose={() => setDetailModalOpen(false)}
        modalHeading="通话详情"
        passiveModal
        size="lg"
      >
        {selectedCall && (
          <div style={{ padding: '1rem' }}>
            <h4>基本信息</h4>
            <div style={{ marginBottom: '1rem' }}>
              <p><strong>来电者:</strong> {selectedCall.caller_name || '未知'}</p>
              <p><strong>号码:</strong> {selectedCall.counterpart}</p>
              <p><strong>状态:</strong> {getStatusTag(selectedCall.status)}</p>
              <p><strong>处理方式:</strong> {getHandlerDisplay(selectedCall.handler_type)}</p>
              <p><strong>时长:</strong> {formatDuration(selectedCall.duration_seconds)}</p>
              {selectedCall.ai_confidence && (
                <p><strong>AI置信度:</strong> {selectedCall.ai_confidence}%</p>
              )}
            </div>

            {selectedCall.summary && (
              <>
                <h4>通话摘要</h4>
                <p style={{ marginBottom: '1rem' }}>{selectedCall.summary}</p>
              </>
            )}

            {selectedCall.transcript && (
              <>
                <h4>对话记录</h4>
                <pre style={{
                  whiteSpace: 'pre-wrap',
                  backgroundColor: 'var(--cds-layer-01)',
                  padding: '1rem',
                  borderRadius: '4px',
                  fontSize: '0.875rem',
                  lineHeight: '1.5',
                }}>
                  {selectedCall.transcript}
                </pre>
              </>
            )}
          </div>
        )}
      </Modal>
    </PageTemplate>
  );
}
