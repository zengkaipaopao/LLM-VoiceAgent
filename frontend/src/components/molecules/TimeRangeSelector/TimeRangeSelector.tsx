/**
 * TimeRangeSelector - 时间范围和粒度选择器
 * 
 * Molecule组件，用于选择图表的时间范围和数据粒度
 * 符合Carbon Design System规范
 */
import { useState } from 'react';
import { DatePicker, DatePickerInput, Dropdown } from '@carbon/react';
import './TimeRangeSelector.scss';

export type Granularity = 'hour' | 'day' | 'week' | 'month' | 'year';

export interface TimeRangeSelectorProps {
  /** 开始日期 */
  startDate?: Date;
  /** 结束日期 */
  endDate?: Date;
  /** 数据粒度 */
  granularity?: Granularity;
  /** 开始日期变化回调 */
  onStartDateChange?: (date: Date) => void;
  /** 结束日期变化回调 */
  onEndDateChange?: (date: Date) => void;
  /** 粒度变化回调 */
  onGranularityChange?: (granularity: Granularity) => void;
}

const granularityOptions = [
  { id: 'hour', label: '小时' },
  { id: 'day', label: '天' },
  { id: 'week', label: '周' },
  { id: 'month', label: '月' },
  { id: 'year', label: '年' },
];

export function TimeRangeSelector({
  startDate,
  endDate,
  granularity = 'day',
  onStartDateChange,
  onEndDateChange,
  onGranularityChange,
}: TimeRangeSelectorProps) {
  const [internalStartDate, setInternalStartDate] = useState<Date>(
    startDate || new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) // 默认7天前
  );
  const [internalEndDate, setInternalEndDate] = useState<Date>(
    endDate || new Date()
  );

  const handleStartDateChange = (dates: Date[]) => {
    if (dates && dates[0]) {
      setInternalStartDate(dates[0]);
      onStartDateChange?.(dates[0]);
    }
  };

  const handleEndDateChange = (dates: Date[]) => {
    if (dates && dates[0]) {
      setInternalEndDate(dates[0]);
      onEndDateChange?.(dates[0]);
    }
  };

  const handleGranularityChange = ({ selectedItem }: any) => {
    if (selectedItem) {
      onGranularityChange?.(selectedItem.id as Granularity);
    }
  };

  return (
    <div className="time-range-selector">
      <div className="time-range-selector__group">
        <DatePicker
          datePickerType="single"
          value={internalStartDate}
          onChange={handleStartDateChange}
        >
          <DatePickerInput
            id="start-date-picker"
            placeholder="mm/dd/yyyy"
            labelText="开始日期"
            size="md"
          />
        </DatePicker>

        <DatePicker
          datePickerType="single"
          value={internalEndDate}
          onChange={handleEndDateChange}
        >
          <DatePickerInput
            id="end-date-picker"
            placeholder="mm/dd/yyyy"
            labelText="结束日期"
            size="md"
          />
        </DatePicker>

        <Dropdown
          id="granularity-selector"
          titleText="数据粒度"
          label="选择粒度"
          items={granularityOptions}
          itemToString={(item) => (item ? item.label : '')}
          selectedItem={granularityOptions.find((opt) => opt.id === granularity)}
          onChange={handleGranularityChange}
          size="md"
          className="time-range-selector__granularity"
        />
      </div>
    </div>
  );
}
