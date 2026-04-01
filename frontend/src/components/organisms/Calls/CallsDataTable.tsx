import { useCallback, useMemo } from 'react';
import { TableToolbarAction, TableToolbarMenu } from '@carbon/react';

import { FilterConfig, Header, SmartDataTable } from '../DataTable/SmartDataTable';
import { CallTableRow } from '../../../hooks/useCallsPage';
import { CallLog } from '../../../types/shared';
import {
  CallHandlerLabels,
  CallStatusLabels,
  buildCallHandlerLabels,
  buildCallStatusLabels,
  buildCallsFilterConfig,
  buildCallsHeaders,
} from './callsDataTableConfig';
import { renderCallsTableCell } from './CallsDataTableCellRenderer';

type TranslateFn = (key: string) => string;

interface CallsDataTableProps {
  rows: CallTableRow[];
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
  onViewCall: (call: CallLog) => void;
  t: TranslateFn;
}

export function CallsDataTable({
  rows,
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
  onViewCall,
  t,
}: CallsDataTableProps) {
  const filterConfig = useMemo<FilterConfig[]>(() => buildCallsFilterConfig(t), [t]);
  const headers = useMemo<Header[]>(() => buildCallsHeaders(t), [t]);
  const statusLabels = useMemo<CallStatusLabels>(() => buildCallStatusLabels(t), [t]);
  const handlerLabels = useMemo<CallHandlerLabels>(() => buildCallHandlerLabels(t), [t]);
  const renderCell = useCallback(
    (cellValue: unknown, cellKey: string, row: CallTableRow) =>
      renderCallsTableCell({
        cellValue,
        cellKey,
        row,
        statusLabels,
        handlerLabels,
        onViewCall,
        t,
      }),
    [handlerLabels, onViewCall, statusLabels, t]
  );

  return (
    <SmartDataTable
      rows={rows}
      headers={headers}
      loading={loading}
      totalItems={totalItems}
      page={page}
      pageSize={pageSize}
      onSearch={onSearch}
      searchPlaceholder={t('calls.table.toolbar.searchPlaceholder')}
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
            Refresh
          </TableToolbarAction>
          <TableToolbarAction onClick={() => {}}>Export Data</TableToolbarAction>
        </TableToolbarMenu>
      }
      renderCell={renderCell}
    />
  );
}
