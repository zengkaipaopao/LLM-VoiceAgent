import { FilterConfig } from '../DataTable/SmartDataTable';

type TranslateFn = (key: string) => string;

export interface AppointmentOperationLabels {
  create: string;
  update: string;
  cancel: string;
}

export function buildAppointmentOperationLabels(t: TranslateFn): AppointmentOperationLabels {
  return {
    create: t('pages:appointments.table.operations.create'),
    update: t('pages:appointments.table.operations.update'),
    cancel: t('pages:appointments.table.operations.cancel'),
  };
}

export function buildAppointmentsFilterConfig(t: TranslateFn): FilterConfig[] {
  return [
    {
      key: 'timestamp',
      label: t('pages:appointments.table.headers.timestamp'),
      type: 'date-range',
    },
    {
      key: 'operation',
      label: t('pages:appointments.table.headers.operation'),
      options: [
        { label: t('pages:appointments.table.operations.create'), value: 'create' },
        { label: t('pages:appointments.table.operations.update'), value: 'update' },
        { label: t('pages:appointments.table.operations.cancel'), value: 'cancel' },
      ],
    },
    {
      key: 'is_handled',
      label: t('pages:appointments.table.headers.handledStatus'),
      options: [
        { label: t('pages:appointments.table.status.handled'), value: 'true' },
        { label: t('pages:appointments.table.status.unhandled'), value: 'false' },
      ],
    },
  ];
}

export function normalizeAppointmentCellText(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return '-';
  }
  return String(value);
}
