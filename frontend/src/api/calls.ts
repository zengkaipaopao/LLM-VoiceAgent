import { http } from './http';
import { CallLog, CallDirection, CallStatus } from '../types/shared';

type ApiCallLog = {
  id: string;
  direction: CallDirection | string;
  counterpart: string;
  started_at: string;
  duration_seconds: number;
  status: CallStatus | string;
  summary?: string | null;
};

type PaginatedCallResponse = {
  data: ApiCallLog[];
  total: number;
};

const mapCall = (call: ApiCallLog): CallLog => ({
  id: call.id,
  direction: call.direction as CallDirection,
  counterpart: call.counterpart,
  startedAt: call.started_at,
  durationSeconds: call.duration_seconds,
  status: call.status as CallStatus,
  summary: call.summary ?? undefined,
});

export async function fetchCalls() {
  const response = await http.get<PaginatedCallResponse>('/calls');
  return {
    data: response.data.data.map(mapCall),
    total: response.data.total,
  };
}
