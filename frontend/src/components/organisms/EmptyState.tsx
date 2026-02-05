import { ReactNode } from 'react';
import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  title,
  description,
  icon,
  action,
  className = '' 
}: EmptyStateProps) {
  const { t } = useTranslation(['common']);
  
  // Use i18n for default values
  const finalTitle = title || t('common:emptyState.title');
  const finalDescription = description || t('common:emptyState.description');
  
  return (
    <Tile className={`empty-state ${className}`.trim()}>
      <div className="empty-state__content">
        {icon && <div className="empty-state__icon">{icon}</div>}
        <h3 className="empty-state__title">{finalTitle}</h3>
        {finalDescription && (
          <p className="empty-state__description">{finalDescription}</p>
        )}
        {action && (
          <div className="empty-state__action">{action}</div>
        )}
      </div>
    </Tile>
  );
}
