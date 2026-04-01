import { Appointment, PromptTemplate } from '../../types/shared';
import { resolveAppointmentAmount } from '../../utils/appointmentFields';
import { AppointmentTableRow, DynamicSchemaField } from './types';

type TranslateFn = (key: string) => string;

type TableHeader = {
  key: string;
  header: string;
};

interface BuildAppointmentQueryParamsOptions {
  page: number;
  pageSize: number;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  selectedPromptId: string;
  searchQuery: string;
  selectedFilters: Record<string, any[]>;
}

export function normalizeSchemaFields(schema: unknown): DynamicSchemaField[] {
  if (!schema || typeof schema !== 'object') {
    return [];
  }

  const maybeSchema = schema as { fields?: unknown };
  if (!Array.isArray(maybeSchema.fields)) {
    return [];
  }

  return maybeSchema.fields
    .map((field): DynamicSchemaField | null => {
      if (typeof field === 'string') {
        return { name: field };
      }

      if (field && typeof field === 'object') {
        const candidate = field as { name?: unknown; label?: unknown };
        if (typeof candidate.name === 'string' && candidate.name.trim() !== '') {
          return {
            name: candidate.name.trim(),
            label: typeof candidate.label === 'string' ? candidate.label : undefined,
          };
        }
      }

      return null;
    })
    .filter((field): field is DynamicSchemaField => field !== null);
}

function toIsoStartDate(value: string | number | Date): string {
  const startDate = new Date(value);
  startDate.setHours(0, 0, 0, 0);
  return startDate.toISOString();
}

function toIsoEndDate(value: string | number | Date): string {
  const endDate = new Date(value);
  endDate.setHours(23, 59, 59, 999);
  return endDate.toISOString();
}

export function buildAppointmentQueryParams({
  page,
  pageSize,
  sortBy,
  sortOrder,
  selectedPromptId,
  searchQuery,
  selectedFilters,
}: BuildAppointmentQueryParamsOptions): Record<string, string> {
  const params: Record<string, string> = {
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    order: sortOrder,
    prompt_id: selectedPromptId,
  };

  if (searchQuery) {
    params.search = searchQuery;
  }

  const operationFilters = selectedFilters.operation;
  if (operationFilters?.length) {
    params.operation = operationFilters.map((value) => String(value)).join(',');
  }

  const handledFilters = selectedFilters.is_handled;
  if (handledFilters?.length === 1) {
    params.is_handled = String(handledFilters[0]);
  }

  const timestampFilters = selectedFilters.timestamp;
  if (timestampFilters?.length === 2) {
    const [start, end] = timestampFilters;
    if (start) {
      params.start_date = toIsoStartDate(start as string | number | Date);
    }
    if (end) {
      params.end_date = toIsoEndDate(end as string | number | Date);
    }
  }

  return params;
}

export function buildAppointmentBaseHeaders(t: TranslateFn): TableHeader[] {
  return [
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
  ];
}

export function buildAppointmentHeaders(
  baseHeaders: TableHeader[],
  availablePrompts: PromptTemplate[],
  selectedPromptId: string
): TableHeader[] {
  const selectedPrompt = availablePrompts.find((prompt) => prompt.id === selectedPromptId);
  const schemaFields = normalizeSchemaFields(selectedPrompt?.extractionSchema);
  const hasFieldConfig = schemaFields.length > 0;

  const actionHeader = baseHeaders.find((header) => header.key === 'actions');
  let otherHeaders = baseHeaders.filter((header) => header.key !== 'actions');

  if (hasFieldConfig) {
    const essentialKeys = ['timestamp', 'operation', 'is_handled'];
    otherHeaders = otherHeaders.filter((header) => essentialKeys.includes(header.key));
  }

  const staticHeaderKeys = new Set(otherHeaders.map((header) => header.key));
  const seenDynamicKeys = new Set<string>();
  const dynamicHeaders = hasFieldConfig
    ? schemaFields
        .map((field) => {
          const name = field.name.trim();
          if (!name || staticHeaderKeys.has(name) || seenDynamicKeys.has(name)) return null;
          seenDynamicKeys.add(name);
          return {
            key: `dynamic_${name}`,
            header: field.label || name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' '),
          };
        })
        .filter((header): header is TableHeader => !!header)
    : [];

  return actionHeader
    ? [...otherHeaders, ...dynamicHeaders, actionHeader]
    : [...otherHeaders, ...dynamicHeaders];
}

function resolveAppointmentAddress(
  appointment: Appointment,
  extracted: Record<string, unknown>
): string {
  return (
    appointment.address ||
    (typeof extracted.pickup_address === 'string' ? extracted.pickup_address : undefined) ||
    (typeof extracted.address === 'string' ? extracted.address : undefined) ||
    '-'
  );
}

function applyDynamicExtractedData(
  rowContent: AppointmentTableRow,
  extractedData: Record<string, unknown> | undefined
): void {
  if (!extractedData) return;

  Object.entries(extractedData).forEach(([key, value]) => {
    rowContent[`dynamic_${key}`] = typeof value === 'object' ? JSON.stringify(value) : value;
  });
}

function applyLegacyFallback(rowContent: AppointmentTableRow, appointment: Appointment): void {
  const legacyFallback: Record<string, unknown> = {
    caller_name: appointment.caller_name,
    company: appointment.company,
    category: appointment.category,
    amount: appointment.amount,
    address: appointment.address,
    summary: appointment.summary,
    extra_request: appointment.extra_request,
    appointment: appointment.appointment,
    operation: appointment.operation,
    is_handled: appointment.is_handled,
    pickup_address: appointment.address,
    appointment_time: appointment.appointment,
    appointment_content: appointment.summary,
    special_notes: appointment.extra_request,
    request_type: appointment.operation,
    estimated_volume_m3: appointment.amount,
    waste_type: appointment.category,
  };

  Object.entries(legacyFallback).forEach(([key, value]) => {
    const dynamicKey = `dynamic_${key}`;
    if (rowContent[dynamicKey] !== undefined) return;
    if (value === undefined || value === null || value === '') return;
    rowContent[dynamicKey] = typeof value === 'object' ? JSON.stringify(value) : value;
  });
}

export function mapAppointmentsToTableRows(appointments: Appointment[]): AppointmentTableRow[] {
  return appointments.map((appointment) => {
    const extracted = (appointment.extracted_data || {}) as Record<string, unknown>;
    const resolvedAmount = resolveAppointmentAmount({
      amount: appointment.amount,
      extractedData: extracted,
      summary: appointment.summary,
      appointmentContent:
        typeof extracted.appointment_content === 'string' ? extracted.appointment_content : undefined,
    });

    const rowContent: AppointmentTableRow = {
      id: appointment.id,
      timestamp: appointment.timestamp,
      appointment: appointment.appointment,
      operation: appointment.operation || 'create',
      is_handled: appointment.is_handled,
      caller_name: appointment.caller_name,
      company: appointment.company || '-',
      category: appointment.category || '-',
      amount: resolvedAmount,
      address: resolveAppointmentAddress(appointment, extracted),
      summary: appointment.summary || '-',
      extra_request: appointment.extra_request || '-',
      raw: appointment,
    };

    applyDynamicExtractedData(
      rowContent,
      appointment.extracted_data as Record<string, unknown> | undefined
    );
    applyLegacyFallback(rowContent, appointment);

    return rowContent;
  });
}
