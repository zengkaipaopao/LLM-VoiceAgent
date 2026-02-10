/**
 * Custom Hook for managing calls list data
 * 
 * This hook encapsulates the logic for fetching, filtering, and paginating calls.
 * It uses React Query for data fetching and caching.
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { useState, useEffect } from 'react';

// TODO: Import from centralized types file
interface Call {
  id: string;
  direction: 'inbound' | 'outbound';
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
}

interface CallsResponse {
  items: Call[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface CallsFilters {
  status?: string[];
  handler_type?: string[];
  created_at?: [string, string];
  search?: string;
}

interface UseCallsListOptions {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  filters?: CallsFilters;
  enabled?: boolean;
}

/**
 * Fetch calls from API
 */
async function fetchCalls(options: UseCallsListOptions): Promise<CallsResponse> {
  const {
    page = 1,
    pageSize = 20,
    sortBy = 'started_at',
    sortOrder = 'desc',
    filters = {},
  } = options;

  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    order: sortOrder,
    filter_match: 'or',
  });

  // Apply search filter
  if (filters.search) {
    params.append('search', filters.search);
  }

  // Apply status filter
  if (filters.status?.length) {
    params.append('status', filters.status.join(','));
  }

  // Apply handler type filter
  if (filters.handler_type?.length) {
    params.append('handler_type', filters.handler_type.join(','));
  }

  // Apply date range filter
  if (filters.created_at?.length === 2) {
    const [start, end] = filters.created_at;
    
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

  const response = await fetch(`/api/v1/calls?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch calls');
  }

  return response.json();
}

/**
 * Custom hook for calls list
 * 
 * @param options - Query options including pagination, sorting, and filters
 * @returns Query result with calls data and metadata
 * 
 * @example
 * ```tsx
 * function CallsPage() {
 *   const { data, isLoading, error } = useCallsList({
 *     page: 1,
 *     pageSize: 20,
 *     filters: { status: ['completed'] }
 *   });
 * 
 *   if (isLoading) return <Loading />;
 *   if (error) return <Error />;
 *   
 *   return <CallsList calls={data.items} />;
 * }
 * ```
 */
export function useCallsList(
  options: UseCallsListOptions = {}
): UseQueryResult<CallsResponse, Error> {
  const {
    page = 1,
    pageSize = 20,
    sortBy = 'started_at',
    sortOrder = 'desc',
    filters = {},
    enabled = true,
  } = options;

  return useQuery({
    queryKey: ['calls', page, pageSize, sortBy, sortOrder, filters],
    queryFn: () => fetchCalls(options),
    enabled,
    // Keep previous data while fetching new data
    placeholderData: (previousData) => previousData,
    // Cache for 30 seconds
    staleTime: 30 * 1000,
  });
}

/**
 * Hook for managing calls list state with filters
 * 
 * This is a higher-level hook that combines useCallsList with local state management
 * for pagination, sorting, and filtering.
 * 
 * @example
 * ```tsx
 * function CallsPage() {
 *   const {
 *     calls,
 *     isLoading,
 *     page,
 *     pageSize,
 *     total,
 *     filters,
 *     setPage,
 *     setPageSize,
 *     setFilters,
 *     clearFilters,
 *   } = useCallsListWithState();
 * 
 *   return (
 *     <SmartDataTable
 *       rows={calls}
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
export function useCallsListWithState() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState('started_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<CallsFilters>({
    status: [],
    handler_type: [],
  });
  const [searchQuery, setSearchQuery] = useState('');

  // Update filters when search query changes
  useEffect(() => {
    setFilters(prev => ({ ...prev, search: searchQuery }));
  }, [searchQuery]);

  const { data, isLoading, error, refetch } = useCallsList({
    page,
    pageSize,
    sortBy,
    sortOrder,
    filters,
  });

  const clearFilters = () => {
    setFilters({
      status: [],
      handler_type: [],
    });
    setSearchQuery('');
  };

  const handlePageChange = (newPage: number, newPageSize: number) => {
    setPage(newPage);
    setPageSize(newPageSize);
  };

  return {
    // Data
    calls: data?.items || [],
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
