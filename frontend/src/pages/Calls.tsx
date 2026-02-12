import { useState, useEffect, useMemo } from 'react';
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
import { CallLog } from '../types/shared';
// Import dynamically to avoid circle if needed, or static is fine. Using static for cleanliness if possible, but the plan used import(). Stick to dynamic or standard import. Standard is better.
import { fetchCalls } from '../api/calls';

export function Calls() {
  const { t } = useTranslation(['pages', 'common']);
  
  // Filters Configuration
  const filterConfig = useMemo(() => [
    {
      key: 'created_at',
      label: t('calls.table.headers.time'),
      type: 'date-range' as const, 
    },
    {
      key: 'status',
      label: t('calls.table.headers.status'),
      options: [
        { label: t('calls.table.status.completed'), value: 'completed' },
        { label: t('calls.table.status.failed'), value: 'failed' },
        { label: t('calls.table.status.no_answer'), value: 'no_answer' },
        { label: t('calls.table.status.ongoing'), value: 'ongoing' },
      ]
    },
    {
      key: 'handler_type',
      label: t('calls.table.headers.handler'),
      options: [
        { label: t('calls.table.handler.ai'), value: 'ai' },
        { label: t('calls.table.handler.transferred'), value: 'transferred' },
      ]
    }
  ], [t]);

  // State
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Unified Filter State
  const [selectedFilters, setSelectedFilters] = useState<Record<string, any[]>>({
    status: [],
    handler_type: [],
  });

  const [sortBy, setSortBy] = useState('started_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedCall, setSelectedCall] = useState<CallLog | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  // Fetch calls
  const loadCalls = async () => {
    setLoading(true);
    try {
      let startDateStr: string | undefined;
      let endDateStr: string | undefined;

      // Handle Date Range
      if (selectedFilters.created_at?.length === 2) {
        const [start, end] = selectedFilters.created_at;
        
        if (start) {
          const startDate = new Date(start);
          startDate.setHours(0, 0, 0, 0);
          startDateStr = startDate.toISOString();
        }
        
        if (end) {
          const endDate = new Date(end);
          endDate.setHours(23, 59, 59, 999);
          endDateStr = endDate.toISOString();
        }
      }

      const { items, total: totalItems } = await fetchCalls({
        page,
        pageSize,
        sortBy,
        sortOrder,
        status: selectedFilters.status,
        handlerType: selectedFilters.handler_type,
        startDate: startDateStr,
        endDate: endDateStr,
        search: searchQuery,
        filterMatch: 'or', // Explicitly request OR logic for status/handler
      });

      setCalls(items);
      setTotal(totalItems);
    } catch (error) {
      console.error('Failed to fetch calls:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Avoid fetching if date range is incomplete (user is still selecting)
    if (selectedFilters.created_at && selectedFilters.created_at.length === 1) {
      return;
    }
    loadCalls();
  }, [page, pageSize, searchQuery, selectedFilters, sortBy, sortOrder]);

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
    caller: call.callerName || call.counterpart,
    status: call.status,
    handler: call.handlerType,
    started_at: call.startedAt,
    duration: call.durationSeconds,
    confidence: call.aiConfidence,
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
        
        // Search & Filter Props
        onSearch={setSearchQuery}
        searchPlaceholder={t('calls.table.toolbar.searchPlaceholder')}
        
        filters={filterConfig}
        selectedFilters={selectedFilters}
        onFilterChange={setSelectedFilters}
        // Clear Filters
        onClearFilters={() => {
          setSelectedFilters({
            status: [],
            handler_type: [],
          });
        }}
        hasActiveFilters={Object.values(selectedFilters).some(arr => arr && arr.length > 0)}
        
        // Actions
        onPageChange={(p, s) => {
           setPage(p);
           setPageSize(s);
        }}
        
        // Toolbar Buttons
        toolbarActions={
          <TableToolbarMenu>
            <TableToolbarAction onClick={() => loadCalls()}>
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
                   setSelectedCall(row.raw as CallLog);
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
