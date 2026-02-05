import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { SmartDataTable } from '../components/organisms/DataTable/SmartDataTable';
import {
  Tag,
  Button,
  Modal,
  TableToolbarMenu,
  TableToolbarAction
} from '@carbon/react';
import {
  View,
  Bot,
  User,
  ArrowsHorizontal,
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

  // Formatters
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

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

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { type: any; label: string }> = {
      completed: { type: 'green', label: t('calls.table.status.completed') },
      ongoing: { type: 'blue', label: t('calls.table.status.ongoing') },
      failed: { type: 'red', label: t('calls.table.status.failed') },
      no_answer: { type: 'gray', label: t('calls.table.status.no_answer') },
      ringing: { type: 'cyan', label: t('calls.table.status.ringing') },
      busy: { type: 'magenta', label: t('calls.table.status.busy') },
    };

    const config = statusMap[status] || { type: 'gray', label: status };
    return <Tag type={config.type} size="sm">{config.label}</Tag>;
  };

  const getHandlerDisplay = (handlerType?: string) => {
    const handlerMap: Record<string, { icon: any; label: string }> = {
      ai: { icon: Bot, label: t('calls.table.handler.ai') },
      human: { icon: User, label: t('calls.table.handler.human') },
      transferred: { icon: ArrowsHorizontal, label: t('calls.table.handler.transferred') },
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

  // Table Configuration
  const headers = [
    { key: 'call_id', header: t('calls.table.headers.callId') },
    { key: 'caller', header: t('calls.table.headers.caller') },
    { key: 'status', header: t('calls.table.headers.status') },
    { key: 'handler', header: t('calls.table.headers.handler') },
    { key: 'started_at', header: t('calls.table.headers.time') },
    { key: 'duration', header: t('calls.table.headers.duration') },
    { key: 'confidence', header: t('calls.table.headers.confidence') },
    { key: 'actions', header: t('calls.table.headers.actions') },
  ];

  // Map backend data to table rows format if necessary, or just use as is if keys match
  // We need to map some fields to match header keys
  const tableRows = calls.map((call) => ({
    id: call.id,
    call_id: call.id.substring(0, 8),
    caller: call.caller_name || call.counterpart,
    status: call.status,
    handler: call.handler_type,
    started_at: call.started_at,
    duration: call.duration_seconds,
    confidence: call.ai_confidence,
    raw: call // Keep raw data for custom access reference
  }));

  return (
    <PageTemplate
      title={t('calls.title')}
      subtitle={t('calls.subtitle')}
    >
      <SmartDataTable
        rows={tableRows}
        headers={headers}
        loading={loading}
        totalItems={total}
        page={page}
        pageSize={pageSize}
        
        // Actions
        onPageChange={(p, s) => {
           setPage(p);
           setPageSize(s);
        }}
        onSearch={setSearchQuery}
        searchPlaceholder={t('calls.table.toolbar.searchPlaceholder')}
        
        // Toolbar Buttons
        toolbarActions={
          <TableToolbarMenu>
            <TableToolbarAction onClick={() => fetchCalls()}>
              Refresh
            </TableToolbarAction>
             <TableToolbarAction onClick={() => {}}>
              Export Data
            </TableToolbarAction>
          </TableToolbarMenu>
        }
        
        // Custom Rendering
        renderCell={(cellValue, cellKey, row) => {
          if (cellKey === 'status') return getStatusTag(cellValue);
          if (cellKey === 'handler') return getHandlerDisplay(cellValue);
          if (cellKey === 'started_at') return formatDate(cellValue);
          if (cellKey === 'duration') return formatDuration(cellValue);
          if (cellKey === 'actions') {
            return (
              <Button
                kind="ghost"
                size="sm"
                hasIconOnly
                renderIcon={View}
                iconDescription={t('calls.table.actions.view')}
                onClick={() => {
                   // row.raw contains the full original object
                   setSelectedCall(row.raw as Call);
                   setDetailModalOpen(true);
                }}
              />
            );
          }
          return cellValue;
        }}
      />

      {/* Call Detail Modal */}
      <Modal
        open={detailModalOpen}
        onRequestClose={() => setDetailModalOpen(false)}
        modalHeading={selectedCall ? `Call Details: ${selectedCall.id}` : 'Details'}
        passiveModal
      >
        {selectedCall && (
            <pre style={{ whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(selectedCall, null, 2)}
            </pre>
        )}
      </Modal>
    </PageTemplate>
  );
}
