import { ReactNode } from 'react';
interface PageTitleProps {
    children: ReactNode;
    className?: string;
}
/**
 * PageTitle 原子组件
 *
 * 用于显示页面主标题,遵循 Carbon Design System 的排版规范
 */
export declare function PageTitle({ children, className }: PageTitleProps): import("react/jsx-runtime").JSX.Element;
export {};
