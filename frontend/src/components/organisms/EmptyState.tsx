import { ReactNode } from 'react';
import { Tile } from '@carbon/react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/**
 * EmptyState 有机体组件
 * 
 * 用于显示空状态页面,提供友好的用户提示
 * 遵循 Carbon Design System 的空状态设计模式
 */
export function EmptyState({ 
  title = '暂无内容',
  description = '此页面正在开发中',
  icon,
  action,
  className = '' 
}: EmptyStateProps) {
  return (
    <Tile className={`empty-state ${className}`.trim()}>
      <div className="empty-state__content">
        {icon && <div className="empty-state__icon">{icon}</div>}
        <h3 className="empty-state__title">{title}</h3>
        {description && (
          <p className="empty-state__description">{description}</p>
        )}
        {action && (
          <div className="empty-state__action">{action}</div>
        )}
      </div>
    </Tile>
  );
}
