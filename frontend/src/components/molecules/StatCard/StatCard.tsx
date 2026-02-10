/**
 * StatCard - 统计数据卡片组件
 * 
 * Molecule组件，用于展示关键业务指标
 * 符合Carbon Design System规范
 */
import { Tile } from '@carbon/react';
import { ArrowUp, ArrowDown } from '@carbon/icons-react';
import './StatCard.scss';

export interface StatCardProps {
  /** 指标标题 */
  label: string;
  /** 主要数值 */
  value: string | number;
  /** 趋势百分比（正数为上升，负数为下降） */
  trend?: number;
  /** 趋势描述文本 */
  trendLabel?: string;
  /** 是否正在加载 */
  loading?: boolean;
}

export function StatCard({
  label,
  value,
  trend,
  trendLabel,
  loading = false,
}: StatCardProps) {
  const hasTrend = trend !== undefined;
  const isPositive = trend && trend > 0;
  const isNegative = trend && trend < 0;

  return (
    <Tile className="stat-card">
      <div className="stat-card__content">
        {/* 标签 */}
        <p className="stat-card__label">{label}</p>

        {/* 主要数值 */}
        <h2 className="stat-card__value">
          {loading ? '...' : value}
        </h2>

        {/* 趋势指示器 */}
        {hasTrend && !loading && (
          <div 
            className={`stat-card__trend ${
              isPositive ? 'stat-card__trend--positive' : ''
            } ${
              isNegative ? 'stat-card__trend--negative' : ''
            }`}
          >
            {isPositive && <ArrowUp size={16} />}
            {isNegative && <ArrowDown size={16} />}
            <span className="stat-card__trend-text">
              {isPositive ? '+' : ''}{trend}%
              {trendLabel && ` ${trendLabel}`}
            </span>
          </div>
        )}
      </div>
    </Tile>
  );
}
