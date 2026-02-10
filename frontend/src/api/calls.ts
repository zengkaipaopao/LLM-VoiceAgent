import { http } from './http';
import { CallLog, CallDirection, CallStatus } from '../types/shared';

type ApiCallLog = {
  id: string;
  direction: string;
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
};

type PaginatedCallResponse = {
  items: ApiCallLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

const mapCall = (call: ApiCallLog): CallLog => ({
  id: call.id,
  direction: call.direction as CallDirection,
  counterpart: call.counterpart,
  callerName: call.caller_name,
  startedAt: call.started_at,
  answeredAt: call.answered_at,
  endedAt: call.ended_at,
  durationSeconds: call.duration_seconds,
  status: call.status as CallStatus,
  handlerType: call.handler_type,
  isAnswered: call.is_answered,
  aiConfidence: call.ai_confidence,
  summary: call.summary ?? undefined,
  transcript: call.transcript,
  createdAt: call.created_at,
});

export type FetchCallsParams = {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  status?: string[];
  handlerType?: string[];
  startDate?: string;
  endDate?: string;
  search?: string;
  filterMatch?: 'and' | 'or';
};

export async function fetchCalls(params: FetchCallsParams = {}) {
  const queryParams = new URLSearchParams();
  
  if (params.page) queryParams.append('page', params.page.toString());
  if (params.pageSize) queryParams.append('page_size', params.pageSize.toString());
  if (params.sortBy) queryParams.append('sort_by', params.sortBy);
  if (params.sortOrder) queryParams.append('order', params.sortOrder);
  
  if (params.status?.length) queryParams.append('status', params.status.join(','));
  if (params.handlerType?.length) queryParams.append('handler_type', params.handlerType.join(','));
  
  if (params.startDate) queryParams.append('start_date', params.startDate);
  if (params.endDate) queryParams.append('end_date', params.endDate);
  
  if (params.search) queryParams.append('search', params.search);
  if (params.filterMatch) queryParams.append('filter_match', params.filterMatch);

  const response = await http.get<PaginatedCallResponse>(`/calls?${queryParams.toString()}`);
  return {
    items: response.data.items.map(mapCall),
    total: response.data.total,
    page: response.data.page,
    pageSize: response.data.page_size,
    totalPages: response.data.total_pages,
  };
}
