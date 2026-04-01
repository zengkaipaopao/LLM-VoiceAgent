import { ChangeEvent, KeyboardEvent, useMemo, useState } from 'react';

import {
  DataRow,
  FilterConfig,
  Header,
} from '../components/organisms/DataTable/SmartDataTable.types';

type SelectOptionLike = {
  value: any;
};

interface UseSmartDataTableStateArgs<T extends DataRow> {
  rows: T[];
  headers: Header[];
  idKey: string;
  filters: FilterConfig[];
  selectedFilters: Record<string, any[]>;
  onSearch?: (query: string) => void;
  onFilterChange?: (filters: Record<string, any[]>) => void;
}

export interface UseSmartDataTableStateResult<T extends DataRow> {
  searchValue: string;
  isFilterOpen: boolean;
  carbonRows: Array<Record<string, any>>;
  handleSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
  handleSearchKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  toggleFilterPanel: () => void;
  handleFilterSelect: (filterKey: string, selectedItems: any) => void;
  resolveOriginalRow: (rowId: string) => T | null;
}

function extractSelectFilterValues(selectedItems: any): any[] {
  if (!Array.isArray(selectedItems)) {
    return [];
  }
  return selectedItems.map((item) => (item as SelectOptionLike).value);
}

function extractDateFilterValues(selectedItems: any): any[] {
  return Array.isArray(selectedItems) ? selectedItems : [];
}

export function useSmartDataTableState<T extends DataRow>({
  rows,
  headers,
  idKey,
  filters,
  selectedFilters,
  onSearch,
  onFilterChange,
}: UseSmartDataTableStateArgs<T>): UseSmartDataTableStateResult<T> {
  const [searchValue, setSearchValue] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const rowsById = useMemo(() => {
    const map = new Map<string, T>();
    rows.forEach((row) => {
      const rowIdValue = row[idKey];
      const rowId = typeof rowIdValue === 'string' ? rowIdValue : row.id;
      map.set(rowId, row);
    });
    return map;
  }, [idKey, rows]);

  const carbonRows = useMemo<Array<Record<string, any>>>(() => {
    return rows.map((row) => {
      const rowIdValue = row[idKey];
      const normalizedId = typeof rowIdValue === 'string' ? rowIdValue : row.id;
      const nextRow: Record<string, any> = {
        id: normalizedId,
        isExpanded: row.isExpanded,
      };

      headers.forEach((header) => {
        if (row[header.key] !== undefined) {
          nextRow[header.key] = row[header.key];
        }
      });

      return nextRow;
    });
  }, [headers, idKey, rows]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextValue = event.target.value;
    setSearchValue(nextValue);
    if (nextValue === '' && onSearch) {
      onSearch('');
    }
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && onSearch) {
      onSearch(searchValue);
    }
  };

  const toggleFilterPanel = () => {
    setIsFilterOpen((current) => !current);
  };

  const handleFilterSelect = (filterKey: string, selectedItems: any) => {
    if (!onFilterChange) {
      return;
    }

    const filterConfig = filters.find((filter) => filter.key === filterKey);
    const nextValue =
      !filterConfig?.type || filterConfig.type === 'select'
        ? extractSelectFilterValues(selectedItems)
        : extractDateFilterValues(selectedItems);

    onFilterChange({
      ...selectedFilters,
      [filterKey]: nextValue,
    });
  };

  const resolveOriginalRow = (rowId: string) => {
    return rowsById.get(rowId) || null;
  };

  return {
    searchValue,
    isFilterOpen,
    carbonRows,
    handleSearchChange,
    handleSearchKeyDown,
    toggleFilterPanel,
    handleFilterSelect,
    resolveOriginalRow,
  };
}
