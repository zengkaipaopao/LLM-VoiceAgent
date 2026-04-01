import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { fetchPrompts } from '../api/prompts';
import { http } from '../api/http';
import { Appointment, PromptTemplate } from '../types/shared';
import { AppointmentListPayload, AppointmentTableRow } from './appointmentsPage/types';
import {
  buildAppointmentBaseHeaders,
  buildAppointmentHeaders,
  buildAppointmentQueryParams,
  mapAppointmentsToTableRows,
} from './appointmentsPage/utils';

export type { AppointmentTableRow } from './appointmentsPage/types';

export interface UseAppointmentsPageResult {
  availablePrompts: PromptTemplate[];
  selectedPromptId: string;
  setSelectedPromptId: (value: string) => void;
  loading: boolean;
  page: number;
  setPage: (value: number) => void;
  pageSize: number;
  setPageSize: (value: number) => void;
  total: number;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  selectedFilters: Record<string, any[]>;
  setSelectedFilters: (value: Record<string, any[]>) => void;
  headers: Array<{ key: string; header: string }>;
  tableRows: AppointmentTableRow[];
  refreshAppointments: () => Promise<void>;
}

export function useAppointmentsPage(t: (key: string) => string): UseAppointmentsPageResult {
  const [availablePrompts, setAvailablePrompts] = useState<PromptTemplate[]>([]);
  const [promptsLoaded, setPromptsLoaded] = useState(false);
  const latestRequestRef = useRef(0);

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  const [selectedFilters, setSelectedFilters] = useState<Record<string, any[]>>({});
  const [selectedPromptId, setSelectedPromptId] = useState('');

  const [sortBy] = useState('timestamp');
  const [sortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    let cancelled = false;

    const loadPrompts = async () => {
      try {
        const templates = await fetchPrompts();
        if (cancelled) return;
        setAvailablePrompts(templates);
        if (templates.length > 0) {
          const basePrompt = templates.find((item) => item.code === 'base_appointment') || templates[0];
          setSelectedPromptId(basePrompt.id);
        }
      } catch (error) {
        console.error('Failed to fetch prompts:', error);
      } finally {
        if (!cancelled) {
          setPromptsLoaded(true);
        }
      }
    };

    void loadPrompts();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshAppointments = useCallback(async () => {
    if (!selectedPromptId) {
      setAppointments([]);
      setTotal(0);
      setLoading(false);
      return;
    }

    const requestId = ++latestRequestRef.current;
    setLoading(true);
    try {
      const params = buildAppointmentQueryParams({
        page,
        pageSize,
        sortBy,
        sortOrder,
        selectedPromptId,
        searchQuery,
        selectedFilters,
      });

      const response = await http.get('/appointments', { params });
      if (requestId !== latestRequestRef.current) return;

      const payload = response.data as AppointmentListPayload;
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
  }, [page, pageSize, searchQuery, selectedFilters, selectedPromptId, sortBy, sortOrder]);

  useEffect(() => {
    if (!promptsLoaded) return;

    const timestampFilters = selectedFilters.timestamp;
    if (timestampFilters && timestampFilters.length === 1) {
      return;
    }
    void refreshAppointments();
  }, [page, pageSize, promptsLoaded, refreshAppointments, searchQuery, selectedFilters, selectedPromptId]);

  const baseHeaders = useMemo(
    () => buildAppointmentBaseHeaders(t),
    [t]
  );

  const headers = useMemo(() => {
    return buildAppointmentHeaders(baseHeaders, availablePrompts, selectedPromptId);
  }, [availablePrompts, baseHeaders, selectedPromptId]);

  const tableRows = useMemo<AppointmentTableRow[]>(() => {
    return mapAppointmentsToTableRows(appointments);
  }, [appointments]);

  return {
    availablePrompts,
    selectedPromptId,
    setSelectedPromptId,
    loading,
    page,
    setPage,
    pageSize,
    setPageSize,
    total,
    searchQuery,
    setSearchQuery,
    selectedFilters,
    setSelectedFilters,
    headers,
    tableRows,
    refreshAppointments,
  };
}
