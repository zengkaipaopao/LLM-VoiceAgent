/**
 * useDashboardStats - Dashboard统计数据Hook
 * 获取预约管理Dashboard的实时统计数据（固定最近7天）
 */
import { useQuery, UseQueryResult } from '@tanstack/react-query';

export interface DashboardStats {
  calls: {
    total: number;
    today: number;
    avg_duration: string;  // 格式化的时长 "HH:MM:SS"
    total_duration: string;
    trend: number;  // 百分比变化
  };
  appointments: {
    total: number;
    today: number;
    pending: number;        // 待处理
    new_today: number;      // 今日新增
    cancelled: number;      // 已取消
    rescheduled: number;    // 已变更
    completed: number;      // 已完成
    completion_rate: number; // 处理率
    trend: number;  // 百分比变化
  };
  trend: Array<{
    date: string;  // YYYY-MM-DD
    value: number;
    group: string;
  }>;
  system_status: {
    database: { status: string; message: string };
    redis: { status: string; message: string };
    ai_service: { status: string; message: string };
  };
}

/**
 * 获取Dashboard统计数据（固定最近7天，天粒度）
 */
async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await fetch('/api/v1/dashboard/stats');
  
  if (!response.ok) {
    throw new Error('Failed to fetch dashboard stats');
  }
  
  return response.json();
}

/**
 * Dashboard统计数据Hook
 * 
 * @param enabled - 是否启用查询
 * @param refetchInterval - 自动刷新间隔（毫秒）
 * @returns Dashboard统计数据
 * 
 * @example
 * ```tsx
 * const { data, isLoading, error } = useDashboardStats();
 * 
 * if (isLoading) return <Loading />;
 * if (error) return <Error />;
 * 
 * return <Dashboard stats={data} />;
 * ```
 */
export function useDashboardStats(
  enabled: boolean = true,
  refetchInterval: number = 60000
): UseQueryResult<DashboardStats, Error> {
  return useQuery({
    queryKey: ['dashboardStats'],
    queryFn: fetchDashboardStats,
    enabled,
    refetchInterval,
    placeholderData: (previousData) => previousData,
    staleTime: 30 * 1000,
  });
}
