import { useTranslation } from 'react-i18next';
import { Grid, Column, Tile, SkeletonText, SkeletonPlaceholder } from '@carbon/react';
import { 
  PhoneVoice, 
  Calendar, 
  Time, 
  Time as ClockIcon,
  Pending,
  Add,
  Close,
  Edit,
  Checkmark,
  ChartLine 
} from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { StatCard } from '../components/molecules/StatCard';
import { StatusIndicator, StatusType } from '../components/molecules/StatusIndicator';
import { CallTrendChart } from '../components/organisms/CallTrendChart';
import { useDashboardStats } from '../hooks/useDashboardStats';
import styles from './Dashboard.module.scss';

/**
 * DashboardPage - 仪表盘页面 - 预约管理中心
 * 
 * 显示预约管理系统概览,包括通话和预约统计
 * 基于Carbon Design System设计规范
 * 数据从后端API实时获取
 */
export function Dashboard() {
  const { t } = useTranslation(['pages', 'common']);

  // 获取Dashboard统计数据（固定最近7天）
  const { data: stats, isLoading, error } = useDashboardStats();

  // Error状态
  if (error && !stats) {
    return (
      <PageTemplate
        title={t('pages:dashboard.title')}
        subtitle={t('pages:dashboard.subtitle')}
      >
        <Tile>
          <p style={{ color: 'var(--cds-text-error)' }}>
            加载Dashboard数据失败: {error.message}
          </p>
        </Tile>
      </PageTemplate>
    );
  }

  // Loading状态（仅首次加载且无缓存数据时显示骨架）
  if (isLoading && !stats) {
    return (
      <PageTemplate
        title={t('pages:dashboard.title')}
        subtitle={t('pages:dashboard.subtitle')}
      >
        <div className={styles.dashboard}>
          <Grid fullWidth className={styles.dashboard__stats}>
            {/* 生成12个skeleton卡片 */}
            {[...Array(12)].map((_, i) => (
              <Column key={i} lg={4} md={4} sm={4}>
                <Tile>
                  <SkeletonText heading />
                  <SkeletonPlaceholder style={{ height: '60px', marginTop: '8px' }} />
                </Tile>
              </Column>
            ))}
          </Grid>
        </div>
      </PageTemplate>
    );
  }

  // 空数据兜底（防止异常状态导致空白）
  if (!stats) {
    return (
      <PageTemplate
        title={t('pages:dashboard.title')}
        subtitle={t('pages:dashboard.subtitle')}
      >
        <Tile>
          <p style={{ color: 'var(--cds-text-secondary)' }}>暂无Dashboard数据</p>
        </Tile>
      </PageTemplate>
    );
  }

  // 解析状态
  const getDatabaseStatus = (): StatusType => {
    const status = stats.system_status.database?.status || 'unknown';
    if (status === 'healthy') return 'online';
    if (status === 'error') return 'error';
    return 'warning';
  };

  const getRedisStatus = (): StatusType => {
    const status = stats.system_status.redis?.status || 'unknown';
    if (status === 'healthy') return 'online';
    if (status === 'error') return 'error';
    return 'warning';
  };

  const getAIServiceStatus = (): StatusType => {
    const status = stats.system_status.ai_service?.status || 'unknown';
    if (status === 'healthy') return 'online';
    if (status === 'error') return 'error';
    return 'warning';
  };

  return (
    <PageTemplate
      title={t('pages:dashboard.title')}
      subtitle={t('pages:dashboard.subtitle')}
    >
      <div className={styles.dashboard}>
        {/* ==================== 统计卡片区 ==================== */}
        <Grid fullWidth className={styles.dashboard__stats}>
          {/* Row 1: 通话统计 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.totalCalls')}
              value={stats.calls.total}
              trend={stats.calls.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.todayCalls')}
              value={stats.calls.today}
              trend={stats.calls.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.avgDuration')}
              value={stats.calls.avg_duration}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.totalDuration')}
              value={stats.calls.total_duration}
            />
          </Column>

          {/* Row 2: 预约概览 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.totalAppointments')}
              value={stats.appointments.total}
              trend={stats.appointments.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.todayAppointments')}
              value={stats.appointments.today}
              trend={stats.appointments.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.pendingAppointments')}
              value={stats.appointments.pending}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.newAppointments')}
              value={stats.appointments.new_today}
            />
          </Column>

          {/* Row 3: 预约详情 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.cancelled')}
              value={stats.appointments.cancelled}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.rescheduled')}
              value={stats.appointments.rescheduled}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.completed')}
              value={stats.appointments.completed}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label={t('pages:dashboard.stats.completionRate')}
              value={`${stats.appointments.completion_rate}%`}
            />
          </Column>
        </Grid>

        {/* ==================== 通话趋势图 ==================== */}
        <section className={styles.dashboard__section}>
          <CallTrendChart data={stats.trend} loading={isLoading} />
        </section>

        {/* ==================== 系统状态 ==================== */}
        <section className={styles.dashboard__section}>
          <Tile className={styles.dashboard__systemStatus}>
            <h3 className={styles.dashboard__sectionTitle}>{t('pages:dashboard.system.title')}</h3>
            <div className={styles.dashboard__statusGrid}>
              <StatusIndicator
                label={t('pages:dashboard.system.postgres')}
                status={getDatabaseStatus()}
                details={stats.system_status.database?.message || t('pages:dashboard.system.unknown')}
              />
              <StatusIndicator
                label={t('pages:dashboard.system.redis')}
                status={getRedisStatus()}
                details={stats.system_status.redis?.message || t('pages:dashboard.system.unknown')}
              />
              <StatusIndicator
                label={t('pages:dashboard.system.aiService')}
                status={getAIServiceStatus()}
                details={stats.system_status.ai_service?.message || t('pages:dashboard.system.unknown')}
              />
            </div>
          </Tile>
        </section>
      </div>
    </PageTemplate>
  );
}
