import { DatePicker, DatePickerInput, MultiSelect } from '@carbon/react';

import { FilterConfig, FilterOption } from './SmartDataTable.types';
import styles from './SmartDataTable.module.scss';

interface SmartDataTableFilterPanelProps {
  visible: boolean;
  filters: FilterConfig[];
  selectedFilters: Record<string, any[]>;
  onFilterSelect: (filterKey: string, selectedItems: any) => void;
}

export function SmartDataTableFilterPanel({
  visible,
  filters,
  selectedFilters,
  onFilterSelect,
}: SmartDataTableFilterPanelProps) {
  if (!visible || filters.length === 0) {
    return null;
  }

  return (
    <div className={styles.filterPanel}>
      <div className={styles.filterGrid}>
        {filters.map((filter) => (
          <div key={filter.key} className={styles.filterItem}>
            {filter.type === 'date-range' ? (
              <DatePicker
                datePickerType="range"
                dateFormat="Y/m/d"
                onChange={(dates: Date[]) => {
                  onFilterSelect(filter.key, dates);
                }}
                value={(selectedFilters[filter.key] || []) as Date[]}
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
                itemToString={(item: FilterOption | null) => (item ? item.label : '')}
                initialSelectedItems={(filter.options || []).filter((option) =>
                  (selectedFilters[filter.key] || []).includes(option.value)
                )}
                onChange={(event: { selectedItems: FilterOption[] }) => {
                  onFilterSelect(filter.key, event.selectedItems);
                }}
                size="md"
                type="default"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
