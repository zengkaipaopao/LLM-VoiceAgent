import { useMemo } from 'react';
import { Column, Grid, SkeletonText, Tag, TagSkeleton, Tile } from '@carbon/react';
import { useAgentsQuery, useCallsQuery } from '../api/hooks';
import styles from './DashboardPage.module.css';

export function DashboardPage() {
  const { data: callsData, isLoading: callsLoading } = useCallsQuery();
  const { data: agents = [], isLoading: agentsLoading } = useAgentsQuery();
  const calls = callsData?.data ?? [];
  const loading = callsLoading || agentsLoading;

  const stats = useMemo(() => {
    const completed = calls.filter((call) => call.status === 'completed').length;
    const failed = calls.filter((call) => call.status === 'failed').length;
    const totalDuration = calls.reduce((sum, call) => sum + call.durationSeconds, 0);
    return {
      total: calls.length,
      completed,
      failed,
      avgDuration: calls.length ? Math.round(totalDuration / calls.length) : 0,
      onlineAgents: agents.length,
    };
  }, [calls, agents]);

  const statCards = [
    { label: '总通话', value: stats.total, helper: '当日' },
    { label: '完成通话', value: stats.completed, helper: '成功' },
    { label: '失败通话', value: stats.failed, helper: '异常' },
    { label: '平均时长（秒）', value: stats.avgDuration, helper: '均值' },
    { label: '在线智能体', value: stats.onlineAgents, helper: '运行中' },
  ];

  return (
    <section className="page-section">
      <h1 className="page-title">仪表盘</h1>
      <p className="page-subtitle">概览当前的呼叫量、成功率和正在运行的智能体。</p>
      <Grid condensed fullWidth>
        {loading
          ? Array.from({ length: 5 }).map((_, index) => (
              <Column key={`stat-skeleton-${index}`} sm={4} md={4} lg={3}>
                <Tile className={styles['stat-tile']}>
                  <SkeletonText width="60%" />
                  <SkeletonText heading width="40%" />
                  <TagSkeleton size="sm" />
                </Tile>
              </Column>
            ))
          : statCards.map((card) => (
              <Column key={card.label} sm={4} md={4} lg={3}>
                <Tile className={styles['stat-tile']}>
                  <span className={styles['stat-label']}>{card.label}</span>
                  <span className={styles['stat-value']}>{card.value}</span>
                  <Tag type="cool-gray">{card.helper}</Tag>
                </Tile>
              </Column>
            ))}
      </Grid>
    </section>
  );
}
