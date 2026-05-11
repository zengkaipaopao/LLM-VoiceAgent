import { FilterConfig, Header } from '../DataTable/SmartDataTable';

type TranslateFn = (key: string) => string;

export interface CallStatusLabels {
  completed: string;
  ongoing: string;
  failed: string;
  noAnswer: string;
  ringing: string;
  busy: string;
}

export interface CallHandlerLabels {
  ai: string;
  human: string;
  transferred: string;
}

export function buildCallsFilterConfig(t: TranslateFn): FilterConfig[] {
  return [
    {
      key: 'created_at',
      label: t('calls.table.headers.time'),
      type: 'date-range',
    },
    {
      key: 'status',
      label: t('calls.table.headers.status'),
      options: [
        { label: t('calls.table.status.completed'), value: 'completed' },
        { label: t('calls.table.status.failed'), value: 'failed' },
        { label: t('calls.table.status.no_answer'), value: 'no_answer' },
        { label: t('calls.table.status.ongoing'), value: 'ongoing' },
      ],
    },
    {
      key: 'handler_type',
      label: t('calls.table.headers.handler'),
      options: [
        { label: t('calls.table.handler.ai'), value: 'ai' },
        { label: t('calls.table.handler.transferred'), value: 'transferred' },
      ],
    },
  ];
}

export function buildCallsHeaders(t: TranslateFn): Header[] {
  return [
    { key: 'call_id', header: t('calls.table.headers.callId') },
    { key: 'caller', header: t('calls.table.headers.caller') },
    { key: 'phone_number', header: t('calls.table.headers.phoneNumber') },
    { key: 'status', header: t('calls.table.headers.status') },
    { key: 'handler', header: t('calls.table.headers.handler') },
    { key: 'started_at', header: t('calls.table.headers.time') },
    { key: 'duration', header: t('calls.table.headers.duration') },
    { key: 'confidence', header: t('calls.table.headers.confidence') },
    { key: 'actions', header: t('calls.table.headers.actions') },
  ];
}

export function buildCallStatusLabels(t: TranslateFn): CallStatusLabels {
  return {
    completed: t('calls.table.status.completed'),
    ongoing: t('calls.table.status.ongoing'),
    failed: t('calls.table.status.failed'),
    noAnswer: t('calls.table.status.no_answer'),
    ringing: t('calls.table.status.ringing'),
    busy: t('calls.table.status.busy'),
  };
}

export function buildCallHandlerLabels(t: TranslateFn): CallHandlerLabels {
  return {
    ai: t('calls.table.handler.ai'),
    human: t('calls.table.handler.human'),
    transferred: t('calls.table.handler.transferred'),
  };
}

export function formatCallDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function formatCallDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
