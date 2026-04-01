import { useTranslation } from 'react-i18next';
import { Column, Grid, SkeletonPlaceholder, SkeletonText, Tile } from '@carbon/react';

import { PageTemplate } from '../components/templates/PageTemplate';
import { CallTrendChart } from '../components/organisms/CallTrendChart';
import { DashboardStatsGrid } from '../components/organisms/Dashboard/DashboardStatsGrid';
import { DashboardSystemStatusPanel } from '../components/organisms/Dashboard/DashboardSystemStatusPanel';
import { useDashboardStats } from '../hooks/useDashboardStats';
import styles from './Dashboard.module.scss';

function DashboardLoadingState() {
  return (
    <div className={styles.dashboard}>
      <Grid fullWidth className={styles.dashboard__stats}>
        {Array.from({ length: 12 }).map((_, index) => (
          <Column key={index} lg={4} md={4} sm={4}>
            <Tile>
              <SkeletonText heading />
              <SkeletonPlaceholder style={{ height: '60px', marginTop: '8px' }} />
            </Tile>
          </Column>
        ))}
      </Grid>
    </div>
  );
}

function DashboardMessageTile({
  message,
  color,
}: {
  message: string;
  color: string;
}) {
  return (
    <Tile>
      <p style={{ color }}>{message}</p>
    </Tile>
  );
}

export function Dashboard() {
  const { t } = useTranslation(['pages', 'common']);
  const { data: stats, isLoading, error } = useDashboardStats();

  if (error && !stats) {
    return (
      <PageTemplate title={t('pages:dashboard.title')} subtitle={t('pages:dashboard.subtitle')}>
        <DashboardMessageTile
          message={`加载Dashboard数据失败: ${error.message}`}
          color="var(--cds-text-error)"
        />
      </PageTemplate>
    );
  }

  if (isLoading && !stats) {
    return (
      <PageTemplate title={t('pages:dashboard.title')} subtitle={t('pages:dashboard.subtitle')}>
        <DashboardLoadingState />
      </PageTemplate>
    );
  }

  if (!stats) {
    return (
      <PageTemplate title={t('pages:dashboard.title')} subtitle={t('pages:dashboard.subtitle')}>
        <DashboardMessageTile
          message="暂无Dashboard数据"
          color="var(--cds-text-secondary)"
        />
      </PageTemplate>
    );
  }

  return (
    <PageTemplate title={t('pages:dashboard.title')} subtitle={t('pages:dashboard.subtitle')}>
      <div className={styles.dashboard}>
        <DashboardStatsGrid stats={stats} className={styles.dashboard__stats} />

        <section className={styles.dashboard__section}>
          <CallTrendChart data={stats.trend} loading={isLoading} />
        </section>

        <section className={styles.dashboard__section}>
          <DashboardSystemStatusPanel
            systemStatus={stats.system_status}
            containerClassName={styles.dashboard__systemStatus}
            titleClassName={styles.dashboard__sectionTitle}
            gridClassName={styles.dashboard__statusGrid}
          />
        </section>
      </div>
    </PageTemplate>
  );
}
