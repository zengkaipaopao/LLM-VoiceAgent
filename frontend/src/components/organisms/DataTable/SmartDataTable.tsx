import React, { useState, useEffect } from 'react';
import {
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  TableBatchActions,
  Pagination,
  DataTableSkeleton,
} from '@carbon/react';
import styles from './SmartDataTable.module.scss';

interface Header {
  key: string;
  header: string;
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
  onSearch?: (query: string) => void;
  searchPlaceholder?: string;
  toolbarActions?: React.ReactNode;
  
  // Cell Rendering
  renderCell?: (cellValue: any, cellKey: string, row: T) => React.ReactNode;
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
  toolbarActions,
  renderCell
}: SmartDataTableProps<T>) {

  const [searchValue, setSearchValue] = useState('');

  // Debounce search
  useEffect(() => {
    if (!onSearch) return;

    const timer = setTimeout(() => {
      onSearch(searchValue);
    }, 500);

    return () => clearTimeout(timer);
  }, [searchValue, onSearch]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchValue(e.target.value);
  };

  if (loading) {
    return (
      <DataTableSkeleton
        columnCount={headers.length}
        rowCount={pageSize}
        headers={headers}
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
          onInputChange // Carbon's internal search handler, we override it
        }: any) => (
          <TableContainer
            title={title}
            description={description}
            {...getTableContainerProps()}
          >
            <TableToolbar {...getToolbarProps()}>
              <TableBatchActions {...getBatchActionProps()}>
                {/* Future: Add Batch Actions here if needed */}
              </TableBatchActions>
              <TableToolbarContent>
                {onSearch && (
                  <TableToolbarSearch
                    onChange={handleSearchChange}
                    // We don't bind 'value' here to keep it uncontrolled-like for Carbon 
                    // or implement fully controlled if Carbon supports it properly.
                    // Carbon TableToolbarSearch is often uncontrolled by default.
                    // But we want to control the input to avoid jank if parent re-renders?
                    // Usually just onChange is enough for internal state.
                    // Let's rely on internal state of Carbon for display, and debounce our callback.
                    // Actually, if we use Carbon's onInputChange, it filters internally.
                    // Since we do server-side search (usually), we ignore Carbon's internal filtering 
                    // by not passing onInputChange to it, or handling it ourselves.
                    
                    placeholder={searchPlaceholder}
                    persistent={true} // Keep it open
                  />
                )}
                {toolbarActions}
              </TableToolbarContent>
            </TableToolbar>
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
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
                    <TableCell colSpan={headers.length} className={styles.emptyCell}>
                      <div className={styles.emptyState}>No data found</div>
                    </TableCell>
                  </TableRow>
                ) : (
                  carbonRows.map((row: any) => {
                     const originalRow = tableRows.find(r => r.id === row.id);
                     if (!originalRow) return null;

                     return (
                      <TableRow key={row.id} {...getRowProps({ row })}>
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
                      </TableRow>
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
