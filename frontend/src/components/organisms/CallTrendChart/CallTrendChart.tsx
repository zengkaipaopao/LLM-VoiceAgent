/**
 * CallTrendChart - 通话趋势图组件
 * 
 * Organism组件，展示通话量趋势
 * 使用Carbon Charts LineChart
 */
import { LineChart } from '@carbon/charts-react';
import '@carbon/charts-react/styles.css';
import { TimeRangeSelector, type Granularity } from '../../molecules/TimeRangeSelector';
import './CallTrendChart.scss';

export interface CallTrendDataPoint {
  date: string;
  value: number;
  group: string;
}

export interface CallTrendChartProps {
  /** 图表数据 */
  data: CallTrendDataPoint[];
  /** 是否正在加载 */
  loading?: boolean;
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

export function CallTrendChart({ 
  data, 
  loading = false,
  startDate,
  endDate,
  granularity = 'day',
  onStartDateChange,
  onEndDateChange,
  onGranularityChange,
}: CallTrendChartProps) {
  // 根据粒度动态设置标题
  const granularityConfig = {
    hour: { title: '通话趋势 (小时)' },
    day: { title: '通话趋势 (天)' },
    week: { title: '通话趋势 (周)' },
    month: { title: '通话趋势 (月)' },
    year: { title: '通话趋势 (年)' },
  };

  const config = granularityConfig[granularity] || granularityConfig.day;

  // 根据粒度设置X轴刻度数量，防止标签拥挤
  const ticksConfig = {
    hour: 24,    // 小时粒度：显示约24个标签
    day: 7,      // 天粒度：显示7个标签
    week: 8,     // 周粒度：显示8个标签
    month: 6,    // 月粒度：显示6个标签
    year: 5,     // 年粒度：显示5个标签
  };

  const options: any = {
    title: config.title,
    axes: {
      left: {
        mapsTo: 'value',
        title: '通话数',
      },
      bottom: {
        mapsTo: 'date',
        scaleType: 'labels',
        // 小时粒度时隐藏标签，避免拥挤
        visible: granularity !== 'hour',
        ticks: {
          max: ticksConfig[granularity] || 7,
          rotation: granularity === 'hour' ? 45 : 0,
        },
      },
    },
    curve: 'curveNatural',
    height: '300px',
    theme: 'g10',
    toolbar: {
      enabled: false,
    },
    legend: {
      enabled: true,
    },
    // 启用tooltip以便在hover时查看具体时间
    tooltip: {
      enabled: true,
    },
  };

  if (loading || data.length === 0) {
    return (
      <div className="call-trend-chart">
        <TimeRangeSelector
          startDate={startDate}
          endDate={endDate}
          granularity={granularity}
          onStartDateChange={onStartDateChange}
          onEndDateChange={onEndDateChange}
          onGranularityChange={onGranularityChange}
        />
        <div className="call-trend-chart__content call-trend-chart__content--loading">
          <p className="call-trend-chart__empty">
            {loading ? '加载中...' : '暂无数据'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="call-trend-chart">
      <TimeRangeSelector
        startDate={startDate}
        endDate={endDate}
        granularity={granularity}
        onStartDateChange={onStartDateChange}
        onEndDateChange={onEndDateChange}
        onGranularityChange={onGranularityChange}
      />
      <div className="call-trend-chart__content">
        <LineChart data={data} options={options} />
      </div>
    </div>
  );
}
