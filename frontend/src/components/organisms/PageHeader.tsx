import { ReactNode } from 'react';
import { PageTitle } from '../atoms/PageTitle';
import { PageSubtitle } from '../atoms/PageSubtitle';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
}

/**
 * PageHeader 有机体组件
 * 
 * 组合页面标题、副标题和操作按钮的复合组件
 * 用于统一页面头部的布局和样式
 */
export function PageHeader({ 
  title, 
  subtitle, 
  actions,
  className = '' 
}: PageHeaderProps) {
  return (
    <div className={`page-header ${className}`.trim()}>
      <div className="page-header__content">
        <PageTitle>{title}</PageTitle>
        {subtitle && <PageSubtitle>{subtitle}</PageSubtitle>}
      </div>
      {actions && (
        <div className="page-header__actions">
          {actions}
        </div>
      )}
    </div>
  );
}
