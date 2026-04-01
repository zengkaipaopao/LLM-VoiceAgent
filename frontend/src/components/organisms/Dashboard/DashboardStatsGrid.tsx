import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Column, Grid } from '@carbon/react';

import { DashboardStats } from '../../../hooks/useDashboardStats';
import { StatCard } from '../../molecules/StatCard';

interface DashboardStatsGridProps {
  stats: DashboardStats;
  className?: string;
}

type StatItem = {
  key: string;
  label: string;
  value: string | number;
  trend?: number;
};

export function DashboardStatsGrid({ stats, className }: DashboardStatsGridProps) {
  const { t } = useTranslation(['pages']);

  const statItems = useMemo<StatItem[]>(
    () => [
      {
        key: 'calls-total',
        label: t('pages:dashboard.stats.totalCalls'),
        value: stats.calls.total,
        trend: stats.calls.trend,
      },
      {
        key: 'calls-today',
        label: t('pages:dashboard.stats.todayCalls'),
        value: stats.calls.today,
        trend: stats.calls.trend,
      },
      {
        key: 'calls-avg-duration',
        label: t('pages:dashboard.stats.avgDuration'),
        value: stats.calls.avg_duration,
      },
      {
        key: 'calls-total-duration',
        label: t('pages:dashboard.stats.totalDuration'),
        value: stats.calls.total_duration,
      },
      {
        key: 'appointments-total',
        label: t('pages:dashboard.stats.totalAppointments'),
        value: stats.appointments.total,
        trend: stats.appointments.trend,
      },
      {
        key: 'appointments-today',
        label: t('pages:dashboard.stats.todayAppointments'),
        value: stats.appointments.today,
        trend: stats.appointments.trend,
      },
      {
        key: 'appointments-pending',
        label: t('pages:dashboard.stats.pendingAppointments'),
        value: stats.appointments.pending,
      },
      {
        key: 'appointments-new',
        label: t('pages:dashboard.stats.newAppointments'),
        value: stats.appointments.new_today,
      },
      {
        key: 'appointments-cancelled',
        label: t('pages:dashboard.stats.cancelled'),
        value: stats.appointments.cancelled,
      },
      {
        key: 'appointments-rescheduled',
        label: t('pages:dashboard.stats.rescheduled'),
        value: stats.appointments.rescheduled,
      },
      {
        key: 'appointments-completed',
        label: t('pages:dashboard.stats.completed'),
        value: stats.appointments.completed,
      },
      {
        key: 'appointments-completion-rate',
        label: t('pages:dashboard.stats.completionRate'),
        value: `${stats.appointments.completion_rate}%`,
      },
    ],
    [stats, t]
  );

  return (
    <Grid fullWidth className={className}>
      {statItems.map((item) => (
        <Column key={item.key} lg={4} md={4} sm={4}>
          <StatCard label={item.label} value={item.value} trend={item.trend} />
        </Column>
      ))}
    </Grid>
  );
}
