import { useState, useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { http } from '../api/http';
import { SmartDataTable } from '../components/organisms/DataTable/SmartDataTable';
import {
  Button,
  TableToolbarMenu,
  TableToolbarAction,
  Dropdown,
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
import { resolveAppointmentAmount } from '../utils/appointmentFields';
import { Appointment, AppointmentsResponse, PromptTemplate } from '../types/shared';

export function Appointments() {
  const { t } = useTranslation(['pages', 'common']);
  
  // State for available prompts
  const [availablePrompts, setAvailablePrompts] = useState<PromptTemplate[]>([]);
  const [promptsLoaded, setPromptsLoaded] = useState(false);
  const latestRequestRef = useRef(0);

  // Fetch prompts on mount
  useEffect(() => {
    const fetchPrompts = async () => {
      try {
        const response = await http.get('/prompts');
        const templates = response.data?.data?.templates || [];
        
        if (templates.length > 0) {
          setAvailablePrompts(templates);
          
          // Auto-select base_appointment or the first available prompt
          const basePrompt = templates.find((p: any) => p.code === 'base_appointment');
          if (basePrompt) {
            setSelectedPromptId(basePrompt.id);
          } else {
            setSelectedPromptId(templates[0].id);
          }
        }
      } catch (error) {
        console.error('Failed to fetch prompts:', error);
      } finally {
        setPromptsLoaded(true);
      }
    };
    fetchPrompts();
  }, []);
  
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
    },
    {
      key: 'is_handled',
      label: t('pages:appointments.table.headers.handledStatus'),
      options: [
        { label: t('pages:appointments.table.status.handled'), value: 'true' },
        { label: t('pages:appointments.table.status.unhandled'), value: 'false' },
      ]
    }
  ], [t, availablePrompts]);

  // State
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Filter State
  const [selectedFilters, setSelectedFilters] = useState<Record<string, any[]>>({});
  
  // Try to set default to base_appointment if available, else first item, else empty string.
  // We'll initialize as empty string and let useEffect set it once prompts load.
  const [selectedPromptId, setSelectedPromptId] = useState<string>('');

  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  // Fetch appointments
  const fetchAppointments = async () => {
    if (!selectedPromptId) {
      setAppointments([]);
      setTotal(0);
      setLoading(false);
      return;
    }

    const requestId = ++latestRequestRef.current;
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        order: sortOrder,
      };

      if (searchQuery) params.search = searchQuery;
      if (selectedFilters.operation?.length) params.operation = selectedFilters.operation.join(',');
      if (selectedFilters.is_handled?.length === 1) params.is_handled = selectedFilters.is_handled[0];
      params.prompt_id = selectedPromptId;

      if (selectedFilters.timestamp?.length === 2) {
        const [start, end] = selectedFilters.timestamp;
        if (start) {
          const startDate = new Date(start);
          startDate.setHours(0, 0, 0, 0);
          params.start_date = startDate.toISOString();
        }
        if (end) {
          const endDate = new Date(end);
          endDate.setHours(23, 59, 59, 999);
          params.end_date = endDate.toISOString();
        }
      }

      const response = await http.get('/appointments', { params });
      const payload = response.data;

      // Ignore stale responses to prevent old unfiltered data overwriting latest selection.
      if (requestId !== latestRequestRef.current) return;

      if (payload && Array.isArray(payload.data)) {
        setAppointments(payload.data);
        setTotal(payload.meta?.pagination?.total_items || 0);
      } else {
        setAppointments([]);
        setTotal(0);
      }
    } catch (error) {
        console.error('Failed to fetch appointments:', error);
    } finally {
      if (requestId === latestRequestRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!promptsLoaded) return;

    // Avoid fetching if date range is incomplete (user is still selecting)
    if (selectedFilters.timestamp && selectedFilters.timestamp.length === 1) {
      return;
    }
    fetchAppointments();
  }, [page, pageSize, searchQuery, selectedFilters, sortBy, sortOrder, selectedPromptId, promptsLoaded]);



  // Table Configuration Base
  const baseHeaders = useMemo(() => [
    { key: 'timestamp', header: t('pages:appointments.table.headers.timestamp') },
    { key: 'appointment', header: t('pages:appointments.table.headers.appointment') },
    { key: 'operation', header: t('pages:appointments.table.headers.operation') },
    { key: 'is_handled', header: t('pages:appointments.table.headers.handledStatus') },
    { key: 'caller_name', header: t('pages:appointments.table.headers.callerName') },
    { key: 'company', header: t('pages:appointments.table.headers.company') },
    { key: 'category', header: t('pages:appointments.table.headers.category') },
    { key: 'amount', header: t('pages:appointments.table.headers.amount') },
    { key: 'address', header: t('pages:appointments.table.headers.address') },
    { key: 'actions', header: t('pages:appointments.table.headers.actions') },
  ], [t]);

  // Dynamically compute headers
  const headers = useMemo(() => {
    const selectedPrompt = availablePrompts.find(p => p.id === selectedPromptId);
    const schema: any = (selectedPrompt as any)?.extraction_schema || selectedPrompt?.extractionSchema;
    const schemaFields = Array.isArray(schema?.fields)
      ? schema.fields
          .map((f: any) => (typeof f === 'string' ? { name: f } : f))
          .filter((f: any) => typeof f?.name === 'string' && f.name.trim() !== '')
      : [];
    const hasFieldConfig = schemaFields.length > 0;

    const actionHeader = baseHeaders.find(h => h.key === 'actions');
    let otherHeaders = baseHeaders.filter(h => h.key !== 'actions');

    // A prompt is considered "custom table mode" only when fields are explicitly defined.
    if (hasFieldConfig) {
      const essentialKeys = ['timestamp', 'operation', 'is_handled'];
      otherHeaders = otherHeaders.filter(h => essentialKeys.includes(h.key));
    }

    const staticHeaderKeys = new Set(otherHeaders.map(h => h.key));
    const seenDynamicKeys = new Set<string>();
    const dynamicHeaders = hasFieldConfig
      ? schemaFields
          .map((field: any) => {
            const name = field.name.trim();
            if (!name || staticHeaderKeys.has(name) || seenDynamicKeys.has(name)) return null;
            seenDynamicKeys.add(name);
            return {
              key: `dynamic_${name}`,
              header: field.label || name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' '),
            };
          })
          .filter((h: any) => !!h)
      : [];

    return actionHeader
      ? [...otherHeaders, ...dynamicHeaders, actionHeader]
      : [...otherHeaders, ...dynamicHeaders];
  }, [baseHeaders, availablePrompts, selectedPromptId]);

  const tableRows = appointments.map((appt) => {
    const extracted = (appt.extracted_data || {}) as Record<string, any>;
    const resolvedAmount = resolveAppointmentAmount({
      amount: appt.amount,
      extractedData: extracted,
      summary: appt.summary,
      appointmentContent: extracted.appointment_content,
    });
    const resolvedAddress = appt.address || extracted.pickup_address || extracted.address || '-';

    const rowContent: any = {
      id: appt.id,
      timestamp: appt.timestamp,
      appointment: appt.appointment,
      operation: appt.operation || 'create',
      is_handled: appt.is_handled,
      caller_name: appt.caller_name,
      company: appt.company || '-',
      category: appt.category || '-',
      amount: resolvedAmount,
      address: resolvedAddress,
      summary: appt.summary || '-',
      extra_request: appt.extra_request || '-',
      raw: appt
    };
    
    if (appt.extracted_data) {
      Object.entries(appt.extracted_data).forEach(([key, value]) => {
        rowContent[`dynamic_${key}`] = typeof value === 'object' ? JSON.stringify(value) : value;
      });
    }

    // Backward compatibility: many historical rows only have legacy columns, not extracted_data.
    // Fill dynamic_* from legacy fields so custom field-configured tables can still show old records.
    const legacyFallback: Record<string, any> = {
      caller_name: appt.caller_name,
      company: appt.company,
      category: appt.category,
      amount: appt.amount,
      address: appt.address,
      summary: appt.summary,
      extra_request: appt.extra_request,
      appointment: appt.appointment,
      operation: appt.operation,
      is_handled: appt.is_handled,

      // New schema aliases commonly used by custom prompts
      pickup_address: appt.address,
      appointment_time: appt.appointment,
      appointment_content: appt.summary,
      special_notes: appt.extra_request,
      request_type: appt.operation,
      estimated_volume_m3: appt.amount,
      waste_type: appt.category,
    };

    Object.entries(legacyFallback).forEach(([key, value]) => {
      const dynamicKey = `dynamic_${key}`;
      if (rowContent[dynamicKey] !== undefined) return;
      if (value === undefined || value === null || value === '') return;
      rowContent[dynamicKey] = typeof value === 'object' ? JSON.stringify(value) : value;
    });
    
    return rowContent;
  });

  const promptDropdownItems = availablePrompts.map(p => ({ id: p.id, text: p.name }));

  return (
    <PageTemplate
      title={t('pages:appointments.title')}
      subtitle={t('pages:appointments.subtitle')}
    >
      <div style={{ padding: '0 0 1rem 0', width: '320px' }}>
        <Dropdown
          id="prompt-switcher"
          titleText="Select Prompt Context"
          label="Select a prompt"
          items={promptDropdownItems}
          itemToString={(item: any) => (item ? item.text : '')}
          selectedItem={promptDropdownItems.find(item => item.id === selectedPromptId) || null}
          onChange={({ selectedItem }: any) => {
            if (selectedItem) {
              setSelectedPromptId(selectedItem.id);
              setPage(1);
            }
          }}
        />
      </div>
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
        // Clear Filters
        onClearFilters={() => {
          setSelectedFilters({});
          setSearchQuery(''); // Optional: checking if user wants search cleared too. Usually yes for "Clear All".
          // If user specifically meant "Clear Filters" (not search), remove setSearchQuery. 
          // Re-reading: "清空filter". Let's stick to clearing structured filters.
          // But usually "Clear" next to filter button implies clearing the filter panel state.
          // Let's just clear selectedFilters for now as it's safer.
        }}
        hasActiveFilters={Object.keys(selectedFilters).length > 0}
        
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
          
          if (cellKey === 'is_handled') {
             return cellValue ? (
               <div style={{ color: '#198038', display: 'flex', alignItems: 'center', gap: '4px' }}>
                 <CheckmarkFilled size={16} />
                 <span>{t('pages:appointments.table.status.handled')}</span>
               </div>
             ) : (
               <div style={{ color: '#da1e28', display: 'flex', alignItems: 'center', gap: '4px' }}>
                 <ErrorFilled size={16} />
                 <span>{t('pages:appointments.table.status.unhandled')}</span>
               </div>
             );
          }

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
        onSuccess={fetchAppointments}
        appointment={selectedAppointment}
      />
    </PageTemplate>
  );
}
