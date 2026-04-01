import { ChangeEvent, KeyboardEvent, ReactNode } from 'react';
import {
  Button,
  TableBatchActions,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
} from '@carbon/react';
import { Filter, Reset } from '@carbon/icons-react';

interface SmartDataTableToolbarProps {
  onSearch?: (query: string) => void;
  searchValue: string;
  searchPlaceholder: string;
  onSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSearchKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onClearFilters?: () => void;
  hasActiveFilters: boolean;
  hasFilters: boolean;
  isFilterOpen: boolean;
  onToggleFilterPanel: () => void;
  toolbarActions?: ReactNode;
  getToolbarProps: () => any;
  getBatchActionProps: () => any;
}

export function SmartDataTableToolbar({
  onSearch,
  searchValue,
  searchPlaceholder,
  onSearchChange,
  onSearchKeyDown,
  onClearFilters,
  hasActiveFilters,
  hasFilters,
  isFilterOpen,
  onToggleFilterPanel,
  toolbarActions,
  getToolbarProps,
  getBatchActionProps,
}: SmartDataTableToolbarProps) {
  return (
    <TableToolbar {...(getToolbarProps() as any)}>
      <TableBatchActions {...(getBatchActionProps() as any)} />

      <TableToolbarContent>
        {onSearch && (
          <TableToolbarSearch
            onChange={onSearchChange}
            onKeyDown={onSearchKeyDown}
            value={searchValue}
            placeholder={searchPlaceholder}
            persistent
          />
        )}

        {onClearFilters && hasActiveFilters && (
          <Button
            hasIconOnly
            renderIcon={Reset}
            iconDescription="Clear Filters"
            tooltipPosition="bottom"
            kind="tertiary"
            onClick={onClearFilters}
          />
        )}

        {hasFilters && (
          <Button
            hasIconOnly
            renderIcon={Filter}
            iconDescription="Filter"
            tooltipPosition="bottom"
            kind={isFilterOpen ? 'primary' : 'ghost'}
            onClick={onToggleFilterPanel}
          />
        )}

        {toolbarActions}
      </TableToolbarContent>
    </TableToolbar>
  );
}
