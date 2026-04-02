import { useCallback, useMemo } from 'react';
import {
  TableToolbarAction,
  TableToolbarMenu,
} from '@carbon/react';

import {
  FilterConfig,
  Header,
  SmartDataTable,
} from '../DataTable/SmartDataTable';
import {
  AppointmentExpandedContent,
} from '../../molecules/Appointments/AppointmentTableCells';
import { AppointmentTableRow } from '../../../hooks/useAppointmentsPage';
import { Appointment } from '../../../types/shared';
import {
  AppointmentOperationLabels,
  buildAppointmentOperationLabels,
  buildAppointmentsFilterConfig,
} from './appointmentsDataTableConfig';
import { renderAppointmentsTableCell } from './AppointmentsDataTableCellRenderer';
import styles from './AppointmentsDataTable.module.scss';

type TranslateFn = (key: string) => string;

type AppointmentsDataTableProps = {
  rows: AppointmentTableRow[];
  headers: Header[];
  loading: boolean;
  totalItems: number;
  page: number;
  pageSize: number;
  selectedFilters: Record<string, any[]>;
  hasActiveFilters: boolean;
  onSearch: (query: string) => void;
  onFilterChange: (filters: Record<string, any[]>) => void;
  onClearFilters: () => void;
  onPageChange: (page: number, pageSize: number) => void;
  onRefresh: () => Promise<void> | void;
  onViewAppointment: (appointment: Appointment) => void;
  t: TranslateFn;
};

export function AppointmentsDataTable({
  rows,
  headers,
  loading,
  totalItems,
  page,
  pageSize,
  selectedFilters,
  hasActiveFilters,
  onSearch,
  onFilterChange,
  onClearFilters,
  onPageChange,
  onRefresh,
  onViewAppointment,
  t,
}: AppointmentsDataTableProps) {
  const operationLabels = useMemo<AppointmentOperationLabels>(() => buildAppointmentOperationLabels(t), [t]);
  const filterConfig = useMemo<FilterConfig[]>(() => buildAppointmentsFilterConfig(t), [t]);
  const renderCell = useCallback(
    (cellValue: unknown, cellKey: string, row: AppointmentTableRow) =>
      renderAppointmentsTableCell({
        cellValue,
        cellKey,
        row,
        operationLabels,
        onViewAppointment,
        t,
      }),
    [onViewAppointment, operationLabels, t]
  );
  const getRowClassName = useCallback((row: AppointmentTableRow) => {
    if (row.row_state === 'linked-cancel') {
      return styles.rowLinkedCancel;
    }
    if (row.row_state === 'linked-update') {
      return styles.rowLinkedUpdate;
    }
    return undefined;
  }, []);

  return (
    <SmartDataTable
      rows={rows}
      headers={headers}
      loading={loading}
      totalItems={totalItems}
      page={page}
      pageSize={pageSize}
      onSearch={onSearch}
      searchPlaceholder={t('pages:appointments.table.toolbar.searchPlaceholder')}
      filters={filterConfig}
      selectedFilters={selectedFilters}
      onFilterChange={onFilterChange}
      onClearFilters={onClearFilters}
      hasActiveFilters={hasActiveFilters}
      onPageChange={onPageChange}
      toolbarActions={
        <TableToolbarMenu>
          <TableToolbarAction
            onClick={() => {
              void onRefresh();
            }}
          >
            {t('pages:appointments.table.toolbar.refresh')}
          </TableToolbarAction>
          <TableToolbarAction onClick={() => {}}>
            {t('pages:appointments.table.toolbar.export')}
          </TableToolbarAction>
        </TableToolbarMenu>
      }
      renderCell={renderCell}
      getRowClassName={getRowClassName}
      renderExpandedRow={(row) => (
        <AppointmentExpandedContent summary={row.summary} extraRequest={row.extra_request} />
      )}
    />
  );
}
