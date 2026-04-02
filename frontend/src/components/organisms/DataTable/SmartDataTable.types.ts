import { ReactNode } from 'react';

export interface Header {
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
  isExpanded?: boolean;
  [key: string]: any;
};

export interface SmartDataTableProps<T extends DataRow> {
  rows: T[];
  headers: Header[];
  idKey?: string;
  loading?: boolean;
  totalItems?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number, pageSize: number) => void;
  title?: string;
  description?: string;
  onSearch?: (query: string) => void;
  searchPlaceholder?: string;
  filters?: FilterConfig[];
  selectedFilters?: Record<string, any[]>;
  onFilterChange?: (filters: Record<string, any[]>) => void;
  onClearFilters?: () => void;
  hasActiveFilters?: boolean;
  toolbarActions?: ReactNode;
  renderCell?: (cellValue: any, cellKey: string, row: T) => ReactNode;
  renderExpandedRow?: (row: T) => ReactNode;
  getRowClassName?: (row: T) => string | undefined;
}
