/**
 * Custom Hook for managing appointments list data
 * 
 * This hook encapsulates the logic for fetching, filtering, and paginating appointments.
 * It uses React Query for data fetching and caching.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { useState, useEffect } from 'react';

// TODO: Import from centralized types file
interface Appointment {
  id: string;
  customer_name: string;
  customer_phone: string;
  appointment_time: string;
  service_type: string;
  status: string;
  notes?: string;
  call_id?: string;
  created_at: string;
  updated_at: string;
}

interface AppointmentsResponse {
  items: Appointment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface AppointmentFilters {
  status?: string[];
  service_type?: string[];
  appointment_time?: [string, string];
  search?: string;
}

interface UseAppointmentsOptions {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  filters?: AppointmentFilters;
  enabled?: boolean;
}

/**
 * Fetch appointments from API
 */
async function fetchAppointments(options: UseAppointmentsOptions): Promise<AppointmentsResponse> {
  const {
    page = 1,
    pageSize = 20,
    sortBy = 'appointment_time',
    sortOrder = 'desc',
    filters = {},
  } = options;

  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    order: sortOrder,
  });

  // Apply search filter
  if (filters.search) {
    params.append('search', filters.search);
  }

  // Apply status filter
  if (filters.status?.length) {
    params.append('status', filters.status.join(','));
  }

  // Apply service type filter
  if (filters.service_type?.length) {
    params.append('service_type', filters.service_type.join(','));
  }

  // Apply date range filter for appointment time
  if (filters.appointment_time?.length === 2) {
    const [start, end] = filters.appointment_time;
    
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
  
  if (!response.ok) {
    throw new Error('Failed to fetch appointments');
  }

  return response.json();
}

/**
 * Custom hook for appointments list
 * 
 * @param options - Query options including pagination, sorting, and filters
 * @returns Query result with appointments data and metadata
 * 
 * @example
 * ```tsx
 * function AppointmentsPage() {
 *   const { data, isLoading, error } = useAppointments({
 *     page: 1,
 *     pageSize: 20,
 *     filters: { status: ['confirmed'] }
 *   });
 * 
 *   if (isLoading) return <Loading />;
 *   if (error) return <Error />;
 *   
 *   return <AppointmentsList appointments={data.items} />;
 * }
 * ```
 */
export function useAppointments(
  options: UseAppointmentsOptions = {}
): UseQueryResult<AppointmentsResponse, Error> {
  const {
    page = 1,
    pageSize = 20,
    sortBy = 'appointment_time',
    sortOrder = 'desc',
    filters = {},
    enabled = true,
  } = options;

  return useQuery({
    queryKey: ['appointments', page, pageSize, sortBy, sortOrder, filters],
    queryFn: () => fetchAppointments(options),
    enabled,
    // Keep previous data while fetching new data
    placeholderData: (previousData) => previousData,
    // Cache for 30 seconds
    staleTime: 30 * 1000,
  });
}

/**
 * Hook for managing appointments list state with filters
 * 
 * This is a higher-level hook that combines useAppointments with local state management
 * for pagination, sorting, and filtering.
 * 
 * @example
 * ```tsx
 * function AppointmentsPage() {
 *   const {
 *     appointments,
 *     isLoading,
 *     page,
 *     pageSize,
 *     total,
 *     filters,
 *     setPage,
 *     setPageSize,
 *     setFilters,
 *     clearFilters,
 *   } = useAppointmentsWithState();
 * 
 *   return (
 *     <SmartDataTable
 *       rows={appointments}
 *       loading={isLoading}
 *       totalItems={total}
 *       page={page}
 *       pageSize={pageSize}
 *       onPageChange={setPage}
 *       selectedFilters={filters}
 *       onFilterChange={setFilters}
 *       onClearFilters={clearFilters}
 *     />
 *   );
 * }
 * ```
 */
export function useAppointmentsWithState() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState('appointment_time');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<AppointmentFilters>({
    status: [],
    service_type: [],
  });
  const [searchQuery, setSearchQuery] = useState('');

  // Update filters when search query changes
  useEffect(() => {
    setFilters(prev => ({ ...prev, search: searchQuery }));
  }, [searchQuery]);

  const { data, isLoading, error, refetch } = useAppointments({
    page,
    pageSize,
    sortBy,
    sortOrder,
    filters,
  });

  const clearFilters = () => {
    setFilters({
      status: [],
      service_type: [],
    });
    setSearchQuery('');
  };

  const handlePageChange = (newPage: number, newPageSize: number) => {
    setPage(newPage);
    setPageSize(newPageSize);
  };

  return {
    // Data
    appointments: data?.items || [],
    total: data?.total || 0,
    totalPages: data?.total_pages || 0,
    
    // Loading state
    isLoading,
    error,
    
    // Pagination
    page,
    pageSize,
    setPage,
    setPageSize,
    onPageChange: handlePageChange,
    
    // Sorting
    sortBy,
    sortOrder,
    setSortBy,
    setSortOrder,
    
    // Filtering
    filters,
    setFilters,
    clearFilters,
    searchQuery,
    setSearchQuery,
    
    // Actions
    refetch,
  };
}
