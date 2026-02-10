/**
 * useDashboardStats - Dashboard统计数据Hook
 * 从API获取Dashboard的实时统计数据
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';

export interface DashboardStats {
  calls: {
    total: number;
    trend: number;
    success_rate: number;
    ai_handled: number;
    ai_percent: number;
    avg_duration: number;
  };
  appointments: {
    total: number;
    new: number;
    cancelled: number;
    rescheduled: number;
  };
  trend: Array<{
    date: string;
    value: number;
    group: string;
  }>;
  efficiency: Array<{
    group: string;
    value: number;
  }>;
  system_status: {
    postgres: string;
    redis: string;
    llm_api: string;
  };
}

interface UseDashboardStatsOptions {
  startDate?: string;  // YYYY-MM-DD格式
  endDate?: string;    // YYYY-MM-DD格式
  granularity?: 'minute' | 'hour' | 'day' | 'week' | 'month' | 'year';
  enabled?: boolean;
  refetchInterval?: number;
}

/**
 * 获取Dashboard统计数据
 */
async function fetchDashboardStats(
  startDate?: string,
  endDate?: string,
  granularity: string = 'day'
): Promise<DashboardStats> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  params.append('granularity', granularity);
  
  const response = await fetch(`/api/v1/dashboard/stats?${params}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch dashboard stats');
  }
  
  return response.json();
}

/**
 * Dashboard统计数据Hook
 * 
 * @param options - 查询选项
 * @returns Dashboard统计数据
 * 
 * @example
 * ```tsx
 * const { data, isLoading, error } = useDashboardStats({
 *   startDate: '2026-02-01',
 *   endDate: '2026-02-10',
 *   granularity: 'day',
 *   refetchInterval: 60000,
 * });
 * 
 * if (isLoading) return <Loading />;
 * if (error) return <Error />;
 * 
 * return <Dashboard stats={data} />;
 * ```
 */
export function useDashboardStats(
  options: UseDashboardStatsOptions = {}
): UseQueryResult<DashboardStats, Error> {
  const {
    startDate,
    endDate,
    granularity = 'day',
    enabled = true,
    refetchInterval = 60000,
  } = options;

  return useQuery({
    queryKey: ['dashboardStats', startDate, endDate, granularity],
    queryFn: () => fetchDashboardStats(startDate, endDate, granularity),
    enabled,
    refetchInterval,
    placeholderData: (previousData) => previousData,
    staleTime: 30 * 1000,
  });
}
