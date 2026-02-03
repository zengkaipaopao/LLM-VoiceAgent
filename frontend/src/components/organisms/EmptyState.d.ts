import { ReactNode } from 'react';
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
export declare function EmptyState({ title, description, icon, action, className }: EmptyStateProps): import("react/jsx-runtime").JSX.Element;
export {};
