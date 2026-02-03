import { ReactNode } from 'react';
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
export declare function PageHeader({ title, subtitle, actions, className }: PageHeaderProps): import("react/jsx-runtime").JSX.Element;
export {};
