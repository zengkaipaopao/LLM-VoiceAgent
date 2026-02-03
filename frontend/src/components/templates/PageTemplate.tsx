import { ReactNode } from 'react';
import { PageHeader } from '../organisms/PageHeader';

interface PageTemplateProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * PageTemplate 模板组件
 * 
 * 提供统一的页面布局模板
 * 包含页面头部和内容区域
 */
export function PageTemplate({ 
  title, 
  subtitle, 
  actions,
  children,
  className = '' 
}: PageTemplateProps) {
  return (
    <section className={`page-section ${className}`.trim()}>
      <PageHeader 
        title={title} 
        subtitle={subtitle} 
        actions={actions}
      />
      <div className="page-content">
        {children}
      </div>
    </section>
  );
}
