/**
 * CallTrendChart - 通话趋势图组件
 * 
 * Organism组件，展示通话量趋势（固定最近7天，天粒度）
 * 使用Carbon Charts LineChart
 */
import { LineChart } from '@carbon/charts-react';
import '@carbon/charts-react/styles.css';
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
}

export function CallTrendChart({ 
  data, 
  loading = false,
}: CallTrendChartProps) {
  const options: any = {
    title: '最近7天通话趋势',
    axes: {
      left: {
        mapsTo: 'value',
        title: '通话数',
      },
      bottom: {
        mapsTo: 'date',
        scaleType: 'labels',
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
    tooltip: {
      enabled: true,
    },
  };

  if (loading || data.length === 0) {
    return (
      <div className="call-trend-chart">
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
      <div className="call-trend-chart__content">
        <LineChart data={data} options={options} />
      </div>
    </div>
  );
}
