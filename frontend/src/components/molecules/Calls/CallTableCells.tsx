import { ArrowsHorizontal, Bot, User } from '@carbon/icons-react';
import { Tag } from '@carbon/react';

import styles from './CallTableCells.module.scss';

type TagType =
  | 'red'
  | 'magenta'
  | 'purple'
  | 'blue'
  | 'cyan'
  | 'teal'
  | 'green'
  | 'gray'
  | 'cool-gray'
  | 'warm-gray'
  | 'high-contrast'
  | 'outline';

interface CallStatusLabels {
  completed: string;
  ongoing: string;
  failed: string;
  noAnswer: string;
  ringing: string;
  busy: string;
}

interface CallStatusTagProps {
  status: string;
  labels: CallStatusLabels;
}

interface CallHandlerLabels {
  ai: string;
  human: string;
  transferred: string;
}

interface CallHandlerCellProps {
  handlerType?: string;
  labels: CallHandlerLabels;
}

const DEFAULT_STATUS_TAG: { type: TagType; label: string } = {
  type: 'gray',
  label: '-',
};

export function CallStatusTag({ status, labels }: CallStatusTagProps) {
  const statusMap: Record<string, { type: TagType; label: string }> = {
    completed: { type: 'green', label: labels.completed },
    ongoing: { type: 'blue', label: labels.ongoing },
    failed: { type: 'red', label: labels.failed },
    no_answer: { type: 'gray', label: labels.noAnswer },
    ringing: { type: 'cyan', label: labels.ringing },
    busy: { type: 'magenta', label: labels.busy },
  };

  const fallbackLabel = typeof status === 'string' && status.trim().length > 0 ? status : '-';
  const config = statusMap[fallbackLabel] || {
    ...DEFAULT_STATUS_TAG,
    label: fallbackLabel,
  };

  return (
    <Tag type={config.type} size="sm">
      {config.label}
    </Tag>
  );
}

export function CallHandlerCell({ handlerType, labels }: CallHandlerCellProps) {
  const handlerMap: Record<string, { icon: typeof Bot; label: string }> = {
    ai: { icon: Bot, label: labels.ai },
    human: { icon: User, label: labels.human },
    transferred: { icon: ArrowsHorizontal, label: labels.transferred },
  };

  if (!handlerType) {
    return <>-</>;
  }

  const config = handlerMap[handlerType];
  if (!config) {
    return <>{handlerType}</>;
  }

  const Icon = config.icon;
  return (
    <div className={styles.handlerCell}>
      <Icon size={16} />
      <span>{config.label}</span>
    </div>
  );
}
