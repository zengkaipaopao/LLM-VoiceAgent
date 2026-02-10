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
import './DashboardPage.scss';

/**
 * DashboardPage - 仪表盘页面 - 预约管理中心
 * 
 * 显示预约管理系统概览,包括通话和预约统计
 * 基于Carbon Design System设计规范
 * 数据从后端API实时获取
 */
export function DashboardPage() {
  const { t } = useTranslation(['pages', 'common']);

  // 获取Dashboard统计数据（固定最近7天）
  const { data: stats, isLoading, error } = useDashboardStats();

  // Loading状态
  if (isLoading || !stats) {
    return (
      <PageTemplate
        title={t('pages:dashboard.title')}
        subtitle={t('pages:dashboard.subtitle')}
      >
        <div className="dashboard">
          <Grid fullWidth className="dashboard__stats">
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

  // Error状态
  if (error) {
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
      <div className="dashboard">
        {/* ==================== 统计卡片区 ==================== */}
        <Grid fullWidth className="dashboard__stats">
          {/* Row 1: 通话统计 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="总通话数"
              value={stats.calls.total}
              trend={stats.calls.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="今日通话"
              value={stats.calls.today}
              trend={stats.calls.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="平均通话时长"
              value={stats.calls.avg_duration}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="总通话时长"
              value={stats.calls.total_duration}
            />
          </Column>

          {/* Row 2: 预约概览 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="总预约数"
              value={stats.appointments.total}
              trend={stats.appointments.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="今日预约"
              value={stats.appointments.today}
              trend={stats.appointments.trend}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="待处理预约"
              value={stats.appointments.pending}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="新增预约"
              value={stats.appointments.new_today}
            />
          </Column>

          {/* Row 3: 预约详情 */}
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="已取消"
              value={stats.appointments.cancelled}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="已变更"
              value={stats.appointments.rescheduled}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="已完成"
              value={stats.appointments.completed}
            />
          </Column>

          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="处理率"
              value={`${stats.appointments.completion_rate}%`}
            />
          </Column>
        </Grid>

        {/* ==================== 通话趋势图 ==================== */}
        <section className="dashboard__section">
          <CallTrendChart data={stats.trend} loading={isLoading} />
        </section>

        {/* ==================== 系统状态 ==================== */}
        <section className="dashboard__section">
          <Tile className="dashboard__system-status">
            <h3 className="dashboard__section-title">系统状态</h3>
            <div className="dashboard__status-grid">
              <StatusIndicator
                label="PostgreSQL"
                status={getDatabaseStatus()}
                details={stats.system_status.database?.message || '未知'}
              />
              <StatusIndicator
                label="Redis"
                status={getRedisStatus()}
                details={stats.system_status.redis?.message || '未知'}
              />
              <StatusIndicator
                label="AI Service"
                status={getAIServiceStatus()}
                details={stats.system_status.ai_service?.message || '未知'}
              />
            </div>
          </Tile>
        </section>
      </div>
    </PageTemplate>
  );
}
