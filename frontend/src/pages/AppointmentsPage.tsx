import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { SmartDataTable } from '../components/organisms/DataTable/SmartDataTable';
import {
  Button,
  TableToolbarMenu,
  TableToolbarAction,
} from '@carbon/react';
import {
  View,
  CheckmarkFilled,
  InformationFilled,
  ErrorFilled,
  HelpFilled,
} from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { AppointmentDetailModal } from '../components/organisms/AppointmentDetailModal/AppointmentDetailModal';
import { formatJapaneseDate, formatCallTime } from '../utils/formatters';
import { Appointment, AppointmentsResponse } from '../types/shared';

export function AppointmentsPage() {
  const { t } = useTranslation(['pages', 'common']);
  
  // Filters Configuration
  const filterConfig = useMemo(() => [
    {
      key: 'timestamp',
      label: t('pages:appointments.table.headers.timestamp'),
      type: 'date-range' as const, 
    },
    {
      key: 'operation',
      label: t('pages:appointments.table.headers.operation'),
      options: [
        { label: t('pages:appointments.table.operations.create'), value: 'create' },
        { label: t('pages:appointments.table.operations.update'), value: 'update' },
        { label: t('pages:appointments.table.operations.cancel'), value: 'cancel' },
      ]
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
      
      // Apply filters
      if (selectedFilters.operation?.length) {
        params.append('operation', selectedFilters.operation.join(','));
      }
      
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



  // Table Configuration
  const headers = useMemo(() => [
    { key: 'timestamp', header: t('pages:appointments.table.headers.timestamp') },
    { key: 'appointment', header: t('pages:appointments.table.headers.appointment') },
    { key: 'operation', header: t('pages:appointments.table.headers.operation') },
    { key: 'caller_name', header: t('pages:appointments.table.headers.callerName') },
    { key: 'company', header: t('pages:appointments.table.headers.company') },
    { key: 'category', header: t('pages:appointments.table.headers.category') },
    { key: 'amount', header: t('pages:appointments.table.headers.amount') },
    { key: 'address', header: t('pages:appointments.table.headers.address') },
    { key: 'actions', header: t('pages:appointments.table.headers.actions') },
  ], [t]);

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
      title={t('pages:appointments.title')}
      subtitle={t('pages:appointments.subtitle')}
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
        searchPlaceholder={t('pages:appointments.table.toolbar.searchPlaceholder')}
        
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
              {t('pages:appointments.table.toolbar.refresh')}
            </TableToolbarAction>
             <TableToolbarAction onClick={() => {}}>
              {t('pages:appointments.table.toolbar.export')}
            </TableToolbarAction>
          </TableToolbarMenu>
        }
        
        // Custom Rendering
        renderCell={(cellValue, cellKey, row) => {
          if (cellKey === 'timestamp') return formatCallTime(cellValue);
          if (cellKey === 'appointment') return formatJapaneseDate(cellValue);
          
          if (cellKey === 'operation') {
             const map: Record<string, { label: string, color: string, icon: any }> = {
               'create': { label: t('pages:appointments.table.operations.create'), color: '#198038', icon: <CheckmarkFilled size={16} style={{ fill: '#198038' }} /> },
               'update': { label: t('pages:appointments.table.operations.update'), color: '#0043ce', icon: <InformationFilled size={16} style={{ fill: '#0043ce' }} /> },
               'delete': { label: t('pages:appointments.table.operations.cancel'), color: '#da1e28', icon: <ErrorFilled size={16} style={{ fill: '#da1e28' }} /> },
               'cancel': { label: t('pages:appointments.table.operations.cancel'), color: '#da1e28', icon: <ErrorFilled size={16} style={{ fill: '#da1e28' }} /> }
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
               {t('pages:appointments.table.headers.actions')}
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

      <AppointmentDetailModal
        open={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
        appointment={selectedAppointment}
      />
    </PageTemplate>
  );
}
