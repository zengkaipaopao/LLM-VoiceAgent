import { CheckmarkFilled, ErrorFilled, HelpFilled, InformationFilled } from '@carbon/icons-react';

import styles from './AppointmentTableCells.module.scss';

interface AppointmentHandledStatusProps {
  handled: boolean;
  handledLabel: string;
  unhandledLabel: string;
}

interface AppointmentOperationLabels {
  create: string;
  update: string;
  cancel: string;
}

interface AppointmentOperationCellProps {
  operation: string;
  labels: AppointmentOperationLabels;
}

interface AppointmentExpandedContentProps {
  summary: string;
  extraRequest: string;
}

export function AppointmentHandledStatus({
  handled,
  handledLabel,
  unhandledLabel,
}: AppointmentHandledStatusProps) {
  return handled ? (
    <div className={`${styles.statusCell} ${styles.statusHandled}`}>
      <CheckmarkFilled size={16} />
      <span>{handledLabel}</span>
    </div>
  ) : (
    <div className={`${styles.statusCell} ${styles.statusUnhandled}`}>
      <ErrorFilled size={16} />
      <span>{unhandledLabel}</span>
    </div>
  );
}

export function AppointmentOperationCell({ operation, labels }: AppointmentOperationCellProps) {
  const normalizedOperation =
    typeof operation === 'string' && operation.trim().length > 0 ? operation : '-';

  if (normalizedOperation === 'create') {
    return (
      <div className={styles.operationCell}>
        <CheckmarkFilled size={16} className={styles.operationIconCreate} />
        <span>{labels.create}</span>
      </div>
    );
  }

  if (normalizedOperation === 'update') {
    return (
      <div className={styles.operationCell}>
        <InformationFilled size={16} className={styles.operationIconUpdate} />
        <span>{labels.update}</span>
      </div>
    );
  }

  if (normalizedOperation === 'delete' || normalizedOperation === 'cancel') {
    return (
      <div className={styles.operationCell}>
        <ErrorFilled size={16} className={styles.operationIconDelete} />
        <span>{labels.cancel}</span>
      </div>
    );
  }

  return (
    <div className={styles.operationCell}>
      <HelpFilled size={16} className={styles.operationIconFallback} />
      <span>{normalizedOperation}</span>
    </div>
  );
}

export function AppointmentExpandedContent({
  summary,
  extraRequest,
}: AppointmentExpandedContentProps) {
  return (
    <div className={styles.expandedRow}>
      <div className={styles.expandedSection}>
        <strong>摘要:</strong>
        <p className={styles.expandedText}>{summary}</p>
      </div>
      {extraRequest !== '-' && (
        <div className={styles.expandedSection}>
          <strong>特别需求:</strong>
          <p className={styles.expandedText}>{extraRequest}</p>
        </div>
      )}
    </div>
  );
}
