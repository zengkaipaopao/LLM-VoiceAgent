import { ChangeEvent, KeyboardEvent, ReactNode } from 'react';
import {
  DataTable,
  Table,
  TableContainer,
  TableExpandHeader,
  TableHead,
  TableHeader,
  TableRow,
} from '@carbon/react';

import { SmartDataTableFilterPanel } from './SmartDataTableFilterPanel';
import { SmartDataTableToolbar } from './SmartDataTableToolbar';
import { SmartDataTableBody } from './SmartDataTableBody';
import { DataRow, FilterConfig, Header, SmartDataTableProps } from './SmartDataTable.types';

interface SmartDataTableContentProps<T extends DataRow> {
  carbonRows: Array<Record<string, unknown>>;
  headers: Header[];
  title?: string;
  description?: string;
  onSearch?: (query: string) => void;
  searchValue: string;
  searchPlaceholder: string;
  onSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSearchKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  filters: FilterConfig[];
  selectedFilters: Record<string, any[]>;
  onFilterSelect: (filterKey: string, selectedItems: any) => void;
  onClearFilters?: () => void;
  hasActiveFilters: boolean;
  isFilterOpen: boolean;
  onToggleFilterPanel: () => void;
  toolbarActions?: ReactNode;
  renderCell?: SmartDataTableProps<T>['renderCell'];
  renderExpandedRow?: SmartDataTableProps<T>['renderExpandedRow'];
  getRowClassName?: SmartDataTableProps<T>['getRowClassName'];
  resolveOriginalRow: (rowId: string) => T | null;
}

export function SmartDataTableContent<T extends DataRow>({
  carbonRows,
  headers,
  title,
  description,
  onSearch,
  searchValue,
  searchPlaceholder,
  onSearchChange,
  onSearchKeyDown,
  filters,
  selectedFilters,
  onFilterSelect,
  onClearFilters,
  hasActiveFilters,
  isFilterOpen,
  onToggleFilterPanel,
  toolbarActions,
  renderCell,
  renderExpandedRow,
  getRowClassName,
  resolveOriginalRow,
}: SmartDataTableContentProps<T>) {
  return (
    <DataTable
      rows={carbonRows as any}
      headers={headers as any}
      isSortable
      render={({
        rows: tableRows,
        headers: tableHeaders,
        getHeaderProps,
        getRowProps,
        getToolbarProps,
        getBatchActionProps,
        getTableProps,
        getTableContainerProps,
      }: any) => (
        <TableContainer title={title} description={description} {...(getTableContainerProps() as any)}>
          <SmartDataTableToolbar
            onSearch={onSearch}
            searchValue={searchValue}
            searchPlaceholder={searchPlaceholder}
            onSearchChange={onSearchChange}
            onSearchKeyDown={onSearchKeyDown}
            onClearFilters={onClearFilters}
            hasActiveFilters={hasActiveFilters}
            hasFilters={filters.length > 0}
            isFilterOpen={isFilterOpen}
            onToggleFilterPanel={onToggleFilterPanel}
            toolbarActions={toolbarActions}
            getToolbarProps={getToolbarProps}
            getBatchActionProps={getBatchActionProps}
          />

          <SmartDataTableFilterPanel
            visible={isFilterOpen}
            filters={filters}
            selectedFilters={selectedFilters}
            onFilterSelect={onFilterSelect}
          />

          <Table {...(getTableProps() as any)}>
            <TableHead>
              <TableRow>
                {renderExpandedRow && <TableExpandHeader />}
                {tableHeaders.map((header: Header) => {
                  const { key, ...headerProps } = getHeaderProps({ header });
                  return (
                    <TableHeader key={String(key)} {...headerProps}>
                      {header.header}
                    </TableHeader>
                  );
                })}
              </TableRow>
            </TableHead>

            <SmartDataTableBody
              tableRows={tableRows}
              tableHeaders={tableHeaders}
              renderCell={renderCell}
              renderExpandedRow={renderExpandedRow}
              getRowClassName={getRowClassName}
              resolveOriginalRow={resolveOriginalRow}
              getRowProps={getRowProps}
            />
          </Table>
        </TableContainer>
      )}
    />
  );
}
