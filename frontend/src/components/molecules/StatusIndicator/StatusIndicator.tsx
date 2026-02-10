/**
 * StatusIndicator - 系统状态指示器组件
 * 
 * Molecule组件，用于展示服务/系统的健康状态
 * 符合Carbon Design System规范
 */
import { useTranslation } from 'react-i18next';
import { Tag } from '@carbon/react';
import { 
  CheckmarkFilled, 
  WarningFilled, 
  ErrorFilled,
  CircleFilled 
} from '@carbon/icons-react';
import './StatusIndicator.scss';

export type StatusType = 'online' | 'warning' | 'error' | 'unknown';

export interface StatusIndicatorProps {
  /** 服务名称 */
  label: string;
  /** 状态类型 */
  status: StatusType;
  /** 可选的详细信息 */
  details?: string;
  /** 是否显示为紧凑模式 */
  compact?: boolean;
}

const statusConfig = {
  online: {
    icon: CheckmarkFilled,
    tagType: 'green' as const,
    labelKey: 'status.online',
  },
  warning: {
    icon: WarningFilled,
    tagType: 'warm-gray' as const, // Fixed: 'yellow' is not a valid Carbon Tag type
    labelKey: 'status.warning',
  },
  error: {
    icon: ErrorFilled,
    tagType: 'red' as const,
    labelKey: 'status.error',
  },
  unknown: {
    icon: CircleFilled,
    tagType: 'gray' as const,
    labelKey: 'status.unknown',
  },
};

export function StatusIndicator({
  label,
  status,
  details,
  compact = false,
}: StatusIndicatorProps) {
  const { t } = useTranslation('common');
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={`status-indicator ${compact ? 'status-indicator--compact' : ''}`}>
      <div className="status-indicator__main">
        <Icon 
          size={20} 
          className={`status-indicator__icon status-indicator__icon--${status}`}
        />
        <span className="status-indicator__label">{label}</span>
        <Tag type={config.tagType} size="sm">
          {t(config.labelKey)}
        </Tag>
      </div>
      
      {details && !compact && (
        <p className="status-indicator__details">{details}</p>
      )}
    </div>
  );
}
