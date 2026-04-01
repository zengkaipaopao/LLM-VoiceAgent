import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchCalls } from '../api/calls';
import { http } from '../api/http';
import { CallLog } from '../types/shared';
import { CallFilters, CallTableRow } from './callsPage/types';
import { hasActiveCallFilters, mapCallsToTableRows, normalizeCallDateRange } from './callsPage/utils';

const DEFAULT_FILTERS: CallFilters = {
  status: [],
  handler_type: [],
};

export type { CallFilters, CallTableRow } from './callsPage/types';

export interface UseCallsPageResult {
  loading: boolean;
  page: number;
  setPage: (value: number) => void;
  pageSize: number;
  setPageSize: (value: number) => void;
  total: number;
  selectedFilters: CallFilters;
  setSelectedFilters: (filters: CallFilters) => void;
  hasActiveFilters: boolean;
  setSearchQuery: (query: string) => void;
  tableRows: CallTableRow[];
  refreshCalls: () => Promise<void>;
  selectedCall: CallLog | null;
  openCallDetails: (call: CallLog) => void;
  closeCallDetails: () => void;
  detailModalOpen: boolean;
  linkedAppointmentId: string | null;
  loadingLinkedAppointment: boolean;
}

export function useCallsPage(): UseCallsPageResult {
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilters, setSelectedFilters] = useState<CallFilters>(DEFAULT_FILTERS);
  const [sortBy] = useState('started_at');
  const [sortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedCall, setSelectedCall] = useState<CallLog | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [linkedAppointmentId, setLinkedAppointmentId] = useState<string | null>(null);
  const [loadingLinkedAppointment, setLoadingLinkedAppointment] = useState(false);

  const refreshCalls = useCallback(async () => {
    setLoading(true);
    try {
      const { startDate, endDate } = normalizeCallDateRange(selectedFilters);
      const { items, total: totalItems } = await fetchCalls({
        page,
        pageSize,
        sortBy,
        sortOrder,
        status: selectedFilters.status,
        handlerType: selectedFilters.handler_type,
        startDate,
        endDate,
        search: searchQuery,
        filterMatch: 'or',
      });

      setCalls(items);
      setTotal(totalItems);
    } catch (error) {
      console.error('Failed to fetch calls:', error);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, searchQuery, selectedFilters, sortBy, sortOrder]);

  useEffect(() => {
    if (selectedFilters.created_at && selectedFilters.created_at.length === 1) {
      return;
    }
    void refreshCalls();
  }, [refreshCalls, selectedFilters]);

  useEffect(() => {
    const fetchLinkedAppointment = async () => {
      if (!detailModalOpen || !selectedCall?.id) {
        setLinkedAppointmentId(null);
        return;
      }

      setLoadingLinkedAppointment(true);
      try {
        const response = await http.get(`/appointments/by-call/${selectedCall.id}`);
        setLinkedAppointmentId(response.data?.data?.id || null);
      } catch (error: any) {
        if (error?.response?.status !== 404) {
          console.error('Failed to fetch linked appointment:', error);
        }
        setLinkedAppointmentId(null);
      } finally {
        setLoadingLinkedAppointment(false);
      }
    };

    void fetchLinkedAppointment();
  }, [detailModalOpen, selectedCall?.id]);

  const tableRows = useMemo<CallTableRow[]>(
    () => mapCallsToTableRows(calls),
    [calls]
  );

  const hasActiveFilters = useMemo(() => hasActiveCallFilters(selectedFilters), [selectedFilters]);

  const openCallDetails = (call: CallLog) => {
    setSelectedCall(call);
    setDetailModalOpen(true);
  };

  const closeCallDetails = () => {
    setDetailModalOpen(false);
  };

  return {
    loading,
    page,
    setPage,
    pageSize,
    setPageSize,
    total,
    selectedFilters,
    setSelectedFilters,
    hasActiveFilters,
    setSearchQuery,
    tableRows,
    refreshCalls,
    selectedCall,
    openCallDetails,
    closeCallDetails,
    detailModalOpen,
    linkedAppointmentId,
    loadingLinkedAppointment,
  };
}
