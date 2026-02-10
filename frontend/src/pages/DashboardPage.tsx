import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Grid, Column, Tile, SkeletonText, SkeletonPlaceholder } from '@carbon/react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { StatCard } from '../components/molecules/StatCard';
import { StatusIndicator, StatusType } from '../components/molecules/StatusIndicator';
import { CallTrendChart } from '../components/organisms/CallTrendChart';
import { AIEfficiencyChart } from '../components/organisms/AIEfficiencyChart';
import { useDashboardStats } from '../hooks/useDashboardStats';
import type { Granularity } from '../components/molecules/TimeRangeSelector';
import './DashboardPage.scss';

/**
 * DashboardPage - 仪表盘页面
 * 
 * 显示系统概览信息,包括呼叫量、成功率和AI状态
 * 基于Carbon Design System设计规范
 * 数据从后端API实时获取
 */
export function DashboardPage() {
  const { t } = useTranslation(['pages', 'common']);

  // 时间范围状态
  const [startDate, setStartDate] = useState<Date>(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000));
  const [endDate, setEndDate] = useState<Date>(new Date());
  const [granularity, setGranularity] = useState<Granularity>('day');

  // 格式化日期为YYYY-MM-DD
  const formatDate = (date: Date): string => {
    return date.toISOString().split('T')[0];
  };

  // 获取Dashboard统计数据
  const { data: stats, isLoading, error } = useDashboardStats({
    startDate: formatDate(startDate),
    endDate: formatDate(endDate),
    granularity,
    refetchInterval: 60000,
  });

  // 格式化时长（秒 -> 分:秒）
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Loading状态
  if (isLoading || !stats) {
    return (
      <PageTemplate
        title={t('pages:dashboard.title')}
        subtitle={t('pages:dashboard.subtitle')}
      >
        <div className="dashboard">
          <Grid fullWidth className="dashboard__stats">
            {[1, 2, 3, 4, 5].map((i) => (
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

  // 系统状态映射
  const getSystemStatus = (status: string): StatusType => {
    if (status === 'online') return 'online';
    if (status === 'warning') return 'warning';
    if (status === 'error') return 'error';
    return 'unknown';
  };

  return (
    <PageTemplate
      title={t('pages:dashboard.title')}
      subtitle={t('pages:dashboard.subtitle')}
    >
      <div className="dashboard">
        {/* 统计卡片行 - 4个核心指标 */}
        <Grid fullWidth className="dashboard__stats">
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="今日通话"
              value={stats.calls.total}
              trend={stats.calls.trend !== 0 ? stats.calls.trend : undefined}
              trendLabel="vs 昨日"
            />
          </Column>
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="AI处理率"
              value={`${stats.calls.ai_percent}%`}
              trendLabel={`${stats.calls.ai_handled}/${stats.calls.total}通话`}
            />  
          </Column>
          <Column lg={4} md={4} sm={4}>
            <StatCard
              label="平均通话时长"
              value={formatDuration(stats.calls.avg_duration)}
            />
          </Column>
          
          {/* 今日预约统计卡片 */}
          <Column lg={4} md={4} sm={4}>
            <Tile className="dashboard__appointment-tile">
              <p className="stat-card__label">今日预约</p>
              <h2 className="stat-card__value">{stats.appointments.total}</h2>
              <div className="dashboard__appointment-details">
                <div className="dashboard__appointment-item">
                  <span className="dashboard__appointment-dot dashboard__appointment-dot--new" />
                  <span>新预约: {stats.appointments.new}</span>
                </div>
                <div className="dashboard__appointment-item">
                  <span className="dashboard__appointment-dot dashboard__appointment-dot--rescheduled" />
                  <span>变更: {stats.appointments.rescheduled}</span>
                </div>
                <div className="dashboard__appointment-item">
                  <span className="dashboard__appointment-dot dashboard__appointment-dot--cancelled" />
                  <span>取消: {stats.appointments.cancelled}</span>
                </div>
              </div>
            </Tile>
          </Column>
        </Grid>

        {/* 图表行 */}
        <Grid fullWidth className="dashboard__charts">
          <Column lg={8} md={8} sm={4}>
            <Tile>
              <CallTrendChart 
                data={stats.trend}
                startDate={startDate}
                endDate={endDate}
                granularity={granularity}
                onStartDateChange={setStartDate}
                onEndDateChange={setEndDate}
                onGranularityChange={setGranularity}
              />
            </Tile>
          </Column>
          <Column lg={8} md={8} sm={4}>
            <Tile>
              <AIEfficiencyChart 
                data={stats.efficiency} 
                total={stats.calls.total}
              />
            </Tile>
          </Column>
        </Grid>

        {/* 系统状态 */}
        <Grid fullWidth className="dashboard__details">
          <Column lg={16} md={8} sm={4}>
            <Tile>
              <h4 className="dashboard__section-title">系统状态</h4>
              <div className="dashboard__system-status">
                <StatusIndicator
                  label="PostgreSQL"
                  status={getSystemStatus(stats.system_status.postgres)}
                />
                <StatusIndicator
                  label="Redis"
                  status={getSystemStatus(stats.system_status.redis)}
                />
                <StatusIndicator
                  label="LLM API"
                  status={getSystemStatus(stats.system_status.llm_api)}
                />
              </div>
            </Tile>
          </Column>
        </Grid>
      </div>
    </PageTemplate>
  );
}
