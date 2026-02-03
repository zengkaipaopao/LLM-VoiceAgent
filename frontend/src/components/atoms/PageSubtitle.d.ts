import { ReactNode } from 'react';
interface PageSubtitleProps {
    children: ReactNode;
    className?: string;
}
/**
 * PageSubtitle 原子组件
 *
 * 用于显示页面副标题或描述文本,遵循 Carbon Design System 的排版规范
 */
export declare function PageSubtitle({ children, className }: PageSubtitleProps): import("react/jsx-runtime").JSX.Element;
export {};
