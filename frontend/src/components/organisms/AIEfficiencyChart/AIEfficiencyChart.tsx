/**
 * AIEfficiencyChart - AI效率分析图组件
 * 
 * Organism组件，展示AI处理分布
 * 使用Carbon Charts DonutChart
 */
import { DonutChart } from '@carbon/charts-react';
import '@carbon/charts-react/styles.css';
import './AIEfficiencyChart.scss';

export interface AIEfficiencyDataPoint {
  group: string;
  value: number;
}

export interface AIEfficiencyChartProps {
  /** 图表数据 */
  data: AIEfficiencyDataPoint[];
  /** 总计数量（用于中心显示） */
  total?: number;
  /** 是否正在加载 */
  loading?: boolean;
}

export function AIEfficiencyChart({ 
  data, 
  total, 
  loading = false 
}: AIEfficiencyChartProps) {
  const calculatedTotal = total || data.reduce((sum, item) => sum + item.value, 0);

  const options = {
    title: 'AI处理分布',
    resizable: true,
    donut: {
      center: {
        label: `总计: ${calculatedTotal}`,
      },
      alignment: 'center' as const,
    },
    height: '300px',
    theme: 'g10' as const,
    legend: {
      enabled: true,
      alignment: 'center' as const,
    },
    toolbar: {
      enabled: false,
    },
  };

  if (loading || data.length === 0) {
    return (
      <div className="ai-efficiency-chart ai-efficiency-chart--loading">
        <p className="ai-efficiency-chart__empty">
          {loading ? '加载中...' : '暂无数据'}
        </p>
      </div>
    );
  }

  return (
    <div className="ai-efficiency-chart">
      <DonutChart data={data} options={options} />
    </div>
  );
}
