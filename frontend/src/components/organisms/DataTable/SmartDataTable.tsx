import React, { useState, useRef } from 'react';
import {
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableExpandHeader,
  TableExpandRow,
  TableExpandedRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  TableToolbarAction,
  TableBatchActions,
  Pagination,
  DataTableSkeleton,
  MultiSelect,
  Button,
  DatePicker,
  DatePickerInput,
} from '@carbon/react';
import { Filter } from '@carbon/icons-react';
import styles from './SmartDataTable.module.scss';

interface Header {
  key: string;
  header: string;
}

export interface FilterOption {
  label: string;
  value: string | number;
}

export type FilterType = 'select' | 'date-range';

export interface FilterConfig {
  key: string;
  label: string;
  type?: FilterType;
  options?: FilterOption[];
}

export type DataRow = {
  id: string;
  [key: string]: any;
};

interface SmartDataTableProps<T extends DataRow> {
  // Data
  rows: T[];
  headers: Header[];
  idKey?: string; // Default to 'id'
  
  // State
  loading?: boolean;
  
  // Pagination
  totalItems?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number, pageSize: number) => void;
  
  // Toolbar
  title?: string;
  description?: string;
  
  // Search
  onSearch?: (query: string) => void;
  searchPlaceholder?: string;
  
  // Filters
  filters?: FilterConfig[];
  selectedFilters?: Record<string, any[]>;
  onFilterChange?: (filters: Record<string, any[]>) => void;

  // Custom Actions
  toolbarActions?: React.ReactNode;
  
  // Cell Rendering
  renderCell?: (cellValue: any, cellKey: string, row: T) => React.ReactNode;
  
  // Expanded Row Rendering
  renderExpandedRow?: (row: T) => React.ReactNode;
}

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
  toolbarActions,
  renderCell,
  renderExpandedRow
}: SmartDataTableProps<T>) {

  const [searchValue, setSearchValue] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  // Search Handlers
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVal = e.target.value;
    setSearchValue(newVal);
    
    // Clear trigger: if empty, trigger search immediately (reset)
    if (newVal === '' && onSearch) {
      onSearch('');
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && onSearch) {
      onSearch(searchValue);
    }
  };

  // Filter Handlers
  const handleFilterSelect = (filterKey: string, selectedItems: any) => {
    if (onFilterChange) {
      const filterConfig = filters.find(f => f.key === filterKey);
      let valueToStore = selectedItems;

      // For MultiSelect, we extract values from items
      if (!filterConfig?.type || filterConfig.type === 'select') {
         valueToStore = selectedItems.map((item: any) => item.value);
      }
      // For date-range, selectedItems is already Date[], keep as is
      
      const newFilters = {
        ...selectedFilters,
        [filterKey]: valueToStore
      };
      onFilterChange(newFilters);
    }
  };

  if (loading) {
    return (
      <DataTableSkeleton
        columnCount={headers.length}
        rowCount={pageSize}
        headers={headers}
        showToolbar={true} 
      />
    );
  }

  // Preserve rows reference for inner render prop access
  const tableRows = rows;

  return (
    <div className={styles.container}>
      <DataTable rows={rows.map(r => ({ ...r, id: r.id }))} headers={headers} isSortable>
        {({
          rows: carbonRows,
          headers,
          getHeaderProps,
          getRowProps,
          getSelectionProps,
          getToolbarProps,
          getBatchActionProps,
          getTableProps,
          getTableContainerProps,
        }: any) => (
          <TableContainer
            title={title}
            description={description}
            {...getTableContainerProps()}
          >
            <TableToolbar {...getToolbarProps()}>
              {/* Batch Actions Area */}
              <TableBatchActions {...getBatchActionProps()}>
                {/* Future: Add Batch Actions here if needed */}
              </TableBatchActions>
              
              <TableToolbarContent>
                {/* 1. Global Search */}
                {onSearch && (
                  <TableToolbarSearch
                    onChange={handleSearchChange}
                    onKeyDown={handleSearchKeyDown}
                    value={searchValue}
                    placeholder={searchPlaceholder}
                    persistent={true} 
                  />
                )}

                {/* 2. Filter Toggle Action */}
                {filters.length > 0 && (
                  <Button
                    hasIconOnly
                    renderIcon={Filter}
                    iconDescription="Filter"
                    tooltipPosition="bottom"
                    kind={isFilterOpen ? 'primary' : 'ghost'} // Visual feedback for active state
                    onClick={() => setIsFilterOpen(!isFilterOpen)}
                  />
                )}

                {/* 3. Custom Actions (Buttons etc) */}
                {toolbarActions}
              </TableToolbarContent>
            </TableToolbar>
            
            {/* Collapsible Filter Panel */}
            {isFilterOpen && filters.length > 0 && (
              <div className={styles.filterPanel}>
                <div className={styles.filterGrid}>
                  {filters.map((filter) => (
                    <div key={filter.key} className={styles.filterItem}>
                      {filter.type === 'date-range' ? (
                        <DatePicker 
                          datePickerType="range"
                          dateFormat="Y/m/d" // Changed to slash format which is more common/friendly
                          onChange={(dates: Date[]) => {
                            handleFilterSelect(filter.key, dates);
                          }}
                          value={selectedFilters?.[filter.key] || []}
                        >
                          <DatePickerInput
                            id={`filter-${filter.key}-start`}
                            placeholder="yyyy/mm/dd"
                            labelText={`${filter.label} (Start)`}
                            size="md"
                          />
                          <DatePickerInput
                            id={`filter-${filter.key}-end`}
                            placeholder="yyyy/mm/dd"
                            labelText={`${filter.label} (End)`}
                            size="md"
                          />
                        </DatePicker>
                      ) : (
                        <MultiSelect
                          id={`filter-${filter.key}`}
                          label={filter.label}
                          titleText={filter.label}
                          items={filter.options || []}
                          itemToString={(item: any) => (item ? item.label : '')}
                          initialSelectedItems={
                            (filter.options || []).filter(opt => 
                              selectedFilters?.[filter.key]?.includes(opt.value)
                            )
                          }
                          onChange={(e: any) => handleFilterSelect(filter.key, e.selectedItems)}
                          size="md"
                          type="default"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {renderExpandedRow && <TableExpandHeader />}
                  {headers.map((header: any) => (
                    <TableHeader key={header.key} {...getHeaderProps({ header })}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {carbonRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={headers.length + (renderExpandedRow ? 1 : 0)} className={styles.emptyCell}>
                      <div className={styles.emptyState}>No data found</div>
                    </TableCell>
                  </TableRow>
                ) : (
                  carbonRows.map((row: any) => {
                     const originalRow = tableRows.find(r => r.id === row.id);
                     if (!originalRow) return null;

                     const RowComponent = renderExpandedRow ? TableExpandRow : TableRow;

                     return (
                      <React.Fragment key={row.id}>
                        <RowComponent {...getRowProps({ row })} key={row.id}>
                          {row.cells.map((cell: any) => {
                            const cellValue = cell.value;
                            const cellKey = cell.info.header;

                            return (
                              <TableCell key={cell.id}>
                                {renderCell 
                                  ? renderCell(cellValue, cellKey, originalRow) 
                                  : cellValue}
                              </TableCell>
                            );
                          })}
                        </RowComponent>
                        {renderExpandedRow && row.isExpanded && (
                          <TableExpandedRow colSpan={headers.length + 1}>
                             {renderExpandedRow(originalRow)}
                          </TableExpandedRow>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
      
      {onPageChange && (
        <Pagination
          backwardText="Previous page"
          forwardText="Next page"
          itemsPerPageText="Items per page:"
          page={page}
          pageSize={pageSize}
          pageSizes={[10, 20, 50, 100]}
          totalItems={totalItems}
          onChange={(e: { page: number; pageSize: number }) => 
            onPageChange(e.page, e.pageSize)
          }
        />
      )}
    </div>
  );
}
