import { CallLog } from '../../types/shared';
import { CallFilters, CallTableRow } from './types';

export function normalizeCallDateRange(filters: CallFilters): {
  startDate?: string;
  endDate?: string;
} {
  if (!filters.created_at || filters.created_at.length !== 2) {
    return {};
  }

  const [start, end] = filters.created_at;
  const result: { startDate?: string; endDate?: string } = {};

  if (start) {
    const startDate = new Date(start);
    startDate.setHours(0, 0, 0, 0);
    result.startDate = startDate.toISOString();
  }

  if (end) {
    const endDate = new Date(end);
    endDate.setHours(23, 59, 59, 999);
    result.endDate = endDate.toISOString();
  }

  return result;
}

export function mapCallsToTableRows(calls: CallLog[]): CallTableRow[] {
  return calls.map((call) => ({
    id: call.id,
    call_id: call.id.substring(0, 8),
    caller: call.callerName || '-',
    phone_number: call.counterpart || '-',
    status: call.status,
    handler: call.handlerType,
    started_at: call.startedAt,
    duration: call.durationSeconds,
    confidence: call.aiConfidence,
    raw: call,
  }));
}

export function hasActiveCallFilters(selectedFilters: CallFilters): boolean {
  return Object.values(selectedFilters).some((value) => Array.isArray(value) && value.length > 0);
}
