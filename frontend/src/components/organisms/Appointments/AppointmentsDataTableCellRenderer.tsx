import { ReactNode } from 'react';
import { Button } from '@carbon/react';
import { View } from '@carbon/icons-react';

import {
  AppointmentHandledStatus,
  AppointmentOperationCell,
} from '../../molecules/Appointments/AppointmentTableCells';
import { AppointmentTableRow } from '../../../hooks/useAppointmentsPage';
import { Appointment } from '../../../types/shared';
import { formatCallTime, formatJapaneseDate } from '../../../utils/formatters';
import {
  AppointmentOperationLabels,
  normalizeAppointmentCellText,
} from './appointmentsDataTableConfig';
import styles from './AppointmentsDataTable.module.scss';

type TranslateFn = (key: string) => string;

interface RenderAppointmentsTableCellOptions {
  cellValue: unknown;
  cellKey: string;
  row: AppointmentTableRow;
  operationLabels: AppointmentOperationLabels;
  onViewAppointment: (appointment: Appointment) => void;
  t: TranslateFn;
}

export function renderAppointmentsTableCell({
  cellValue,
  cellKey,
  row,
  operationLabels,
  onViewAppointment,
  t,
}: RenderAppointmentsTableCellOptions): ReactNode {
  if (cellKey === 'timestamp') {
    return formatCallTime(String(cellValue ?? ''));
  }

  if (cellKey === 'appointment') {
    return formatJapaneseDate(String(cellValue ?? ''));
  }

  if (cellKey === 'is_handled') {
    return (
      <AppointmentHandledStatus
        handled={Boolean(cellValue)}
        handledLabel={t('pages:appointments.table.status.handled')}
        unhandledLabel={t('pages:appointments.table.status.unhandled')}
      />
    );
  }

  if (cellKey === 'operation') {
    return <AppointmentOperationCell operation={String(cellValue ?? '')} labels={operationLabels} />;
  }

  if (cellKey === 'actions') {
    return (
      <Button
        kind="ghost"
        size="sm"
        renderIcon={View}
        onClick={() => {
          onViewAppointment(row.raw);
        }}
      >
        {t('pages:appointments.table.headers.actions')}
      </Button>
    );
  }

  const normalizedText = normalizeAppointmentCellText(cellValue);
  return (
    <div className={styles.truncatedCell} title={normalizedText}>
      {normalizedText}
    </div>
  );
}
