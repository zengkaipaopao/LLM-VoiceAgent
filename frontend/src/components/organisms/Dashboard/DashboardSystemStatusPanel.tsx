import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { DashboardStats } from '../../../hooks/useDashboardStats';
import { StatusIndicator, StatusType } from '../../molecules/StatusIndicator';

interface DashboardSystemStatusPanelProps {
  systemStatus: DashboardStats['system_status'];
  containerClassName?: string;
  titleClassName?: string;
  gridClassName?: string;
}

function mapStatus(status: string | undefined): StatusType {
  if (status === 'healthy') return 'online';
  if (status === 'error') return 'error';
  return 'warning';
}

export function DashboardSystemStatusPanel({
  systemStatus,
  containerClassName,
  titleClassName,
  gridClassName,
}: DashboardSystemStatusPanelProps) {
  const { t } = useTranslation(['pages']);
  const unknownText = t('pages:dashboard.system.unknown');

  return (
    <Tile className={containerClassName}>
      <h3 className={titleClassName}>{t('pages:dashboard.system.title')}</h3>
      <div className={gridClassName}>
        <StatusIndicator
          label={t('pages:dashboard.system.postgres')}
          status={mapStatus(systemStatus.database?.status)}
          details={systemStatus.database?.message || unknownText}
        />
        <StatusIndicator
          label={t('pages:dashboard.system.redis')}
          status={mapStatus(systemStatus.redis?.status)}
          details={systemStatus.redis?.message || unknownText}
        />
        <StatusIndicator
          label={t('pages:dashboard.system.aiService')}
          status={mapStatus(systemStatus.ai_service?.status)}
          details={systemStatus.ai_service?.message || unknownText}
        />
      </div>
    </Tile>
  );
}
