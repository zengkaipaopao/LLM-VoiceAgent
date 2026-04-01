import { DataTableSkeleton } from '@carbon/react';

import { SmartDataTableContent } from './SmartDataTableContent';
import { SmartDataTablePagination } from './SmartDataTablePagination';
import { DataRow, SmartDataTableProps } from './SmartDataTable.types';
import { useSmartDataTableState } from '../../../hooks/useSmartDataTableState';
import styles from './SmartDataTable.module.scss';

export type {
  DataRow,
  FilterConfig,
  FilterOption,
  FilterType,
  Header,
  SmartDataTableProps,
} from './SmartDataTable.types';

export function SmartDataTable<T extends DataRow>({
  rows,
  headers,
  idKey = 'id',
  loading = false,
  totalItems = 0,
  page = 1,
  pageSize = 10,
  onPageChange,
  title,
  description,
  onSearch,
  searchPlaceholder = 'Search...',
  filters = [],
  selectedFilters = {},
  onFilterChange,
  onClearFilters,
  hasActiveFilters = false,
  toolbarActions,
  renderCell,
  renderExpandedRow,
}: SmartDataTableProps<T>) {
  const {
    searchValue,
    isFilterOpen,
    carbonRows,
    handleSearchChange,
    handleSearchKeyDown,
    toggleFilterPanel,
    handleFilterSelect,
    resolveOriginalRow,
  } = useSmartDataTableState<T>({
    rows,
    headers,
    idKey,
    filters,
    selectedFilters,
    onSearch,
    onFilterChange,
  });

  if (loading) {
    return (
      <DataTableSkeleton
        columnCount={headers.length}
        rowCount={pageSize}
        headers={headers}
        showToolbar
      />
    );
  }

  return (
    <div className={styles.container}>
      <SmartDataTableContent
        carbonRows={carbonRows}
        headers={headers}
        title={title}
        description={description}
        onSearch={onSearch}
        searchValue={searchValue}
        searchPlaceholder={searchPlaceholder}
        onSearchChange={handleSearchChange}
        onSearchKeyDown={handleSearchKeyDown}
        filters={filters}
        selectedFilters={selectedFilters}
        onFilterSelect={handleFilterSelect}
        onClearFilters={onClearFilters}
        hasActiveFilters={hasActiveFilters}
        isFilterOpen={isFilterOpen}
        onToggleFilterPanel={toggleFilterPanel}
        toolbarActions={toolbarActions}
        renderCell={renderCell}
        renderExpandedRow={renderExpandedRow}
        resolveOriginalRow={resolveOriginalRow}
      />

      {onPageChange && (
        <SmartDataTablePagination
          page={page}
          pageSize={pageSize}
          totalItems={totalItems}
          onPageChange={onPageChange}
        />
      )}
    </div>
  );
}
