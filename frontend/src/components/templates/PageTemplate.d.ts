import { ReactNode } from 'react';
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
export declare function PageTemplate({ title, subtitle, actions, children, className }: PageTemplateProps): import("react/jsx-runtime").JSX.Element;
export {};
