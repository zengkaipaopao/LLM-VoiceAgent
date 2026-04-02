import { Fragment } from 'react';
import {
  TableBody,
  TableCell,
  TableExpandRow,
  TableExpandedRow,
  TableRow,
} from '@carbon/react';

import { DataRow, Header, SmartDataTableProps } from './SmartDataTable.types';
import styles from './SmartDataTable.module.scss';

interface SmartDataTableBodyProps<T extends DataRow> {
  tableRows: any[];
  tableHeaders: Header[];
  renderCell?: SmartDataTableProps<T>['renderCell'];
  renderExpandedRow?: SmartDataTableProps<T>['renderExpandedRow'];
  getRowClassName?: SmartDataTableProps<T>['getRowClassName'];
  resolveOriginalRow: (rowId: string) => T | null;
  getRowProps: (params: { row: any }) => Record<string, unknown>;
}

export function SmartDataTableBody<T extends DataRow>({
  tableRows,
  tableHeaders,
  renderCell,
  renderExpandedRow,
  getRowClassName,
  resolveOriginalRow,
  getRowProps,
}: SmartDataTableBodyProps<T>) {
  if (tableRows.length === 0) {
    return (
      <TableBody>
        <TableRow>
          <TableCell
            colSpan={tableHeaders.length + (renderExpandedRow ? 1 : 0)}
            className={styles.emptyCell}
          >
            <div className={styles.emptyState}>No data found</div>
          </TableCell>
        </TableRow>
      </TableBody>
    );
  }

  return (
    <TableBody>
      {tableRows.map((tableRow) => {
        const originalRow = resolveOriginalRow(tableRow.id);
        if (!originalRow) {
          return null;
        }
        const rowProps = getRowProps({ row: tableRow }) as any;
        const customRowClassName = getRowClassName?.(originalRow);
        const mergedRowClassName = [rowProps?.className, customRowClassName]
          .filter((value) => typeof value === 'string' && value.trim().length > 0)
          .join(' ');

        const RowComponent: any = renderExpandedRow ? TableExpandRow : TableRow;

        return (
          <Fragment key={tableRow.id}>
            <RowComponent
              {...rowProps}
              className={mergedRowClassName || rowProps?.className}
            >
              {tableRow.cells.map((cell: any) => (
                <TableCell key={cell.id}>
                  {renderCell
                    ? renderCell(cell.value, cell.info.header, originalRow)
                    : (cell.value as any)}
                </TableCell>
              ))}
            </RowComponent>

            {renderExpandedRow && tableRow.isExpanded && (
              <TableExpandedRow colSpan={tableHeaders.length + 1}>
                {renderExpandedRow(originalRow)}
              </TableExpandedRow>
            )}
          </Fragment>
        );
      })}
    </TableBody>
  );
}
