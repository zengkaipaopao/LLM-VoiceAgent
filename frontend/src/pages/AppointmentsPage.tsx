import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { SmartDataTable } from '../components/organisms/DataTable/SmartDataTable';
import {
  Button,
  Modal,
  TableToolbarMenu,
  TableToolbarAction,
  Tag
} from '@carbon/react';
import {
  View,
  CheckmarkFilled,
  InformationFilled,
  ErrorFilled,
  HelpFilled
} from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';

interface Appointment {
  id: string;
  call_id?: string;
  timestamp: string;
  caller_name: string;
  company?: string;
  appointment: string;
  category?: string;
  amount?: string; // numeric in DB, string here potentially
  address?: string;
  summary?: string;
  extra_request?: string;
  raw_messages?: any;
  operation?: string;
}

interface AppointmentsResponse {
  items: Appointment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function AppointmentsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  // Filters Configuration
  const filterConfig = useMemo(() => [
    {
      key: 'timestamp',
      label: t('calls.table.headers.time') || 'Time', // Reuse or add new translation
      type: 'date-range' as const, 
    }
  ], [t]);

  // State
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Filter State
  const [selectedFilters, setSelectedFilters] = useState<Record<string, any[]>>({});

  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  // Fetch appointments
  const fetchAppointments = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        order: sortOrder,
      });

      if (searchQuery) params.append('search', searchQuery);
      
      // Handle Date Range
      if (selectedFilters.timestamp?.length === 2) {
        const [start, end] = selectedFilters.timestamp;
        
        if (start) {
          const startDate = new Date(start);
          startDate.setHours(0, 0, 0, 0);
          params.append('start_date', startDate.toISOString());
        }
        
        if (end) {
          const endDate = new Date(end);
          endDate.setHours(23, 59, 59, 999);
          params.append('end_date', endDate.toISOString());
        }
      }

      const response = await fetch(`/api/v1/appointments?${params}`);
      const data: AppointmentsResponse = await response.json();

      if (data) {
        setAppointments(data.items);
        setTotal(data.total);
      }
    } catch (error) {
      console.error('Failed to fetch appointments:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Avoid fetching if date range is incomplete (user is still selecting)
    if (selectedFilters.timestamp && selectedFilters.timestamp.length === 1) {
      return;
    }
    fetchAppointments();
  }, [page, pageSize, searchQuery, selectedFilters, sortBy, sortOrder]);

  // Formatters
  const formatJapaneseDate = (dateString: string | Date): string => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return String(dateString);

    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const weekday = weekdays[date.getDay()];
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');

    return `${year}年${month}月${day}日（${weekday}）${hours}:${minutes}:${seconds}`;
  };

  const formatCallTime = (dateString: string | Date): string => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return String(dateString);

    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');

    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
  };

  // Table Configuration
  const headers = [
    { key: 'timestamp', header: '预约时间' },
    { key: 'appointment', header: '希望回收时间' },
    { key: 'operation', header: '操作类型' },
    { key: 'caller_name', header: '客户姓名' },
    { key: 'company', header: '公司/单位' },
    { key: 'category', header: '类别' },
    { key: 'amount', header: '数量' },
    { key: 'address', header: '地址' },
    { key: 'actions', header: '详细内容' },
  ];

  const tableRows = appointments.map((appt) => ({
    id: appt.id,
    timestamp: appt.timestamp,
    appointment: appt.appointment,
    operation: appt.operation || 'create',
    caller_name: appt.caller_name,
    company: appt.company || '-',
    category: appt.category || '-',
    amount: appt.amount || '-',
    address: appt.address || '-',
    summary: appt.summary || '-',
    extra_request: appt.extra_request || '-',
    raw: appt
  }));

  return (
    <PageTemplate
      title={t('pages:appointments.title') || '预约管理'}
      subtitle={t('pages:appointments.subtitle') || '查看所有自动接单助手归档的预约'}
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
        searchPlaceholder="搜索姓名、公司或内容..."
        
        filters={filterConfig}
        selectedFilters={selectedFilters}
        onFilterChange={setSelectedFilters}
        
        // Actions
        onPageChange={(p, s) => {
           setPage(p);
           setPageSize(s);
        }}
        
        // Toolbar Buttons
        toolbarActions={
          <TableToolbarMenu>
            <TableToolbarAction onClick={() => fetchAppointments()}>
              刷新
            </TableToolbarAction>
             <TableToolbarAction onClick={() => {}}>
              导出数据
            </TableToolbarAction>
          </TableToolbarMenu>
        }
        
        // Custom Rendering
        renderCell={(cellValue, cellKey, row) => {
          if (cellKey === 'timestamp') return formatCallTime(cellValue);
          if (cellKey === 'appointment') return formatJapaneseDate(cellValue);
          
          if (cellKey === 'operation') {
             const map: Record<string, { label: string, color: string, icon: any }> = {
               'create': { label: '新预约', color: '#198038', icon: <CheckmarkFilled size={16} style={{ fill: '#198038' }} /> },
               'update': { label: '变更', color: '#0043ce', icon: <InformationFilled size={16} style={{ fill: '#0043ce' }} /> },
               'delete': { label: '取消', color: '#da1e28', icon: <ErrorFilled size={16} style={{ fill: '#da1e28' }} /> },
               'cancel': { label: '取消', color: '#da1e28', icon: <ErrorFilled size={16} style={{ fill: '#da1e28' }} /> }
             };
             const config = map[cellValue as string] || { label: cellValue, color: '#525252', icon: <HelpFilled size={16} style={{ fill: '#525252' }} /> };
             
             return (
               <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                 {config.icon}
                 <span>{config.label}</span>
               </div>
             );
          }
          if (cellKey === 'actions') {
            return (
              <Button
                kind="ghost"
                size="sm"
                renderIcon={View}
                onClick={() => {
                   setSelectedAppointment(row.raw as Appointment);
                   setDetailModalOpen(true);
                }}
              >
               详细内容
              </Button>
            );
          }
          
          // Default string rendering with truncation for others
          return (
            <div 
              style={{ 
                maxWidth: '150px', 
                whiteSpace: 'nowrap', 
                overflow: 'hidden', 
                textOverflow: 'ellipsis' 
              }} 
              title={String(cellValue)} 
            >
              {cellValue}
            </div>
          );
        }}

        // Expanded Row for Summary and Extra Request
        renderExpandedRow={(row) => (
          <div style={{ padding: '1rem', backgroundColor: '#f4f4f4' }}>
            <div style={{ marginBottom: '0.5rem' }}>
              <strong>摘要:</strong>
              <p style={{ margin: '0.5rem 0 1rem 0', whiteSpace: 'pre-wrap' }}>{row.summary}</p>
            </div>
            {row.extra_request && row.extra_request !== '-' && (
              <div>
                <strong>特别需求:</strong>
                <p style={{ margin: '0.5rem 0 0 0', whiteSpace: 'pre-wrap' }}>{row.extra_request}</p>
              </div>
            )}
          </div>
        )}
      />

      {/* Detail Modal */}
      <Modal
        open={detailModalOpen}
        onRequestClose={() => setDetailModalOpen(false)}
        modalHeading={selectedAppointment ? `预约详情: ${selectedAppointment.caller_name}` : '详情'}
        passiveModal
      >
        {selectedAppointment && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* ID Information - Moved to Upper Section */}
                <div style={{ fontSize: '12px', color: '#525252', display: 'grid', gridTemplateColumns: '1fr', gap: '0.25rem', marginTop: '0.5rem' }}>
                    <div><strong>预约事件ID:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedAppointment.id}</span></div>
                    <div><strong>关联通话ID:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedAppointment.call_id || '-'}</span></div>
                </div>
                <hr style={{ border: '0', borderTop: '1px solid #e0e0e0', margin: '0.5rem 0' }} />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div><strong>预约时间:</strong> {formatJapaneseDate(selectedAppointment.timestamp)}</div>
                    <div><strong>希望回收时间:</strong> {formatJapaneseDate(selectedAppointment.appointment)}</div>
                    <div><strong>姓名:</strong> {selectedAppointment.caller_name}</div>
                    <div><strong>公司:</strong> {selectedAppointment.company}</div>
                    <div><strong>类别:</strong> {selectedAppointment.category}</div>
                    <div><strong>数量:</strong> {selectedAppointment.amount}</div>
                </div>
                <div><strong>地址:</strong> {selectedAppointment.address}</div>

                
                <hr style={{ border: '0', borderTop: '1px solid #e0e0e0', margin: '0.5rem 0' }} />
                
                <div><strong>摘要:</strong> {selectedAppointment.summary}</div>
                {selectedAppointment.extra_request && selectedAppointment.extra_request !== '-' && (
                     <div><strong>额外请求:</strong> {selectedAppointment.extra_request}</div>
                )}
                
                {/* Detailed Dialogue Section */}
                {(() => {
                    let messages: any[] = [];
                    try {
                        let raw = selectedAppointment.raw_messages;
                        
                        // Helper to parse string content (handles "obj, obj" pattern)
                        const parseString = (str: string) => {
                            str = str.trim();
                            try {
                                return JSON.parse(str);
                            } catch (e) {
                                try {
                                    return JSON.parse(`[${str}]`);
                                } catch (e2) {
                                    console.warn("Failed to parse dialogue string:", e);
                                    return [];
                                }
                            }
                        };

                        if (typeof raw === 'string') {
                            messages = parseString(raw);
                        } else if (raw && typeof raw === 'object') {
                            if (Array.isArray(raw)) {
                                messages = raw;
                            } else if (Array.isArray(raw.messages)) {
                                messages = raw.messages;
                            } else if (typeof raw.text === 'string') {
                                // Handle case { text: "..." }
                                messages = parseString(raw.text);
                            } else {
                                // Fallback: wrap the object itself if it looks like a message
                                messages = [raw];
                            }
                        }
                    } catch (e) {
                        console.error("Critical error parsing dialogue:", e);
                    }

                    if (!messages || !Array.isArray(messages) || messages.length === 0) return null;

                    return (
                        <div style={{ marginTop: '1rem' }}>
                            <strong style={{ display: 'block', marginBottom: '0.5rem' }}>详细对话:</strong>
                            <div style={{ 
                                backgroundColor: '#ffffff', 
                                border: '1px solid #e0e0e0',
                                padding: '1rem', 
                                borderRadius: '4px',
                                maxHeight: '400px',
                                overflowY: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '1rem'
                            }}>
                                 {messages.map((msg: any, idx: number) => {
                                     const role = msg.role || (msg.is_user ? 'user' : 'assistant');
                                     const isUser = role === 'user';
                                     const content = msg.content || msg.text || JSON.stringify(msg);
                                     
                                     return (
                                         <div key={idx} style={{ 
                                             display: 'flex', 
                                             justifyContent: isUser ? 'flex-end' : 'flex-start',
                                             width: '100%'
                                         }}>
                                             <div style={{
                                                 maxWidth: '80%',
                                                 padding: '0.75rem 1rem',
                                                 borderRadius: '1rem',
                                                 borderBottomRightRadius: isUser ? '2px' : '1rem',
                                                 borderBottomLeftRadius: isUser ? '1rem' : '2px',
                                                 backgroundColor: isUser ? '#0043ce' : '#f4f4f4',
                                                 color: isUser ? '#ffffff' : '#161616',
                                                 fontSize: '0.875rem',
                                                 lineHeight: '1.4',
                                                 boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                                                 whiteSpace: 'pre-wrap'
                                             }} title={msg.ts || ''}>
                                                 <div style={{ fontSize: '0.75rem', marginBottom: '4px', opacity: 0.8 }}>
                                                     {isUser ? '用户' : 'AI助手'}
                                                 </div>
                                                 {content}
                                             </div>
                                         </div>
                                     );
                                 })}
                            </div>
                        </div>
                    );
                })()}
            </div>
        )}
      </Modal>
    </PageTemplate>
  );
}
