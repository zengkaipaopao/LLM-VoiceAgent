import { useMemo } from 'react';
import { Column, Grid, Tag, Tile } from '@carbon/react';
import { useAppState } from '../state/AppStateContext';

export function DashboardPage() {
  const { calls, agents } = useAppState();

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
        {statCards.map((card) => (
          <Column key={card.label} sm={4} md={4} lg={3}>
            <Tile className="stat-tile">
              <span className="stat-label">{card.label}</span>
              <span className="stat-value">{card.value}</span>
              <Tag type="cool-gray">{card.helper}</Tag>
            </Tile>
          </Column>
        ))}
      </Grid>
    </section>
  );
}
