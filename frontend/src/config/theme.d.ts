/**
 * Carbon Design System 主题配置
 *
 * 此文件定义了应用的主题配置,包括颜色、间距、字体等设计令牌
 * 遵循 Carbon Design System 的设计规范
 */
export declare const theme: {
    readonly colors: {
        readonly primary: "var(--cds-interactive-01, #0f62fe)";
        readonly primaryHover: "var(--cds-interactive-01-hover, #0353e9)";
        readonly background: "var(--cds-ui-background, #ffffff)";
        readonly backgroundAlt: "var(--cds-ui-01, #f4f4f4)";
        readonly textPrimary: "var(--cds-text-01, #161616)";
        readonly textSecondary: "var(--cds-text-02, #525252)";
        readonly textPlaceholder: "var(--cds-text-03, #a8a8a8)";
        readonly border: "var(--cds-ui-03, #e0e0e0)";
        readonly borderSubtle: "var(--cds-border-subtle, #e0e0e0)";
        readonly success: "var(--cds-support-02, #24a148)";
        readonly warning: "var(--cds-support-03, #f1c21b)";
        readonly error: "var(--cds-support-01, #da1e28)";
        readonly info: "var(--cds-support-04, #0043ce)";
    };
    readonly spacing: {
        readonly xs: "0.25rem";
        readonly sm: "0.5rem";
        readonly md: "1rem";
        readonly lg: "1.5rem";
        readonly xl: "2rem";
        readonly xxl: "3rem";
    };
    readonly typography: {
        readonly fontFamily: "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif";
        readonly fontSize: {
            readonly xs: "0.75rem";
            readonly sm: "0.875rem";
            readonly base: "1rem";
            readonly lg: "1.125rem";
            readonly xl: "1.25rem";
            readonly '2xl': "1.5rem";
            readonly '3xl': "2rem";
        };
        readonly fontWeight: {
            readonly regular: 400;
            readonly medium: 500;
            readonly semibold: 600;
        };
        readonly lineHeight: {
            readonly tight: 1.25;
            readonly normal: 1.5;
            readonly relaxed: 1.75;
        };
    };
    readonly breakpoints: {
        readonly sm: "320px";
        readonly md: "672px";
        readonly lg: "1056px";
        readonly xl: "1312px";
        readonly max: "1584px";
    };
    readonly shadows: {
        readonly sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)";
        readonly md: "0 2px 6px 0 rgba(0, 0, 0, 0.1)";
        readonly lg: "0 4px 12px 0 rgba(0, 0, 0, 0.15)";
    };
    readonly borderRadius: {
        readonly none: "0";
        readonly sm: "0.125rem";
        readonly md: "0.25rem";
        readonly lg: "0.5rem";
        readonly full: "9999px";
    };
    readonly transitions: {
        readonly fast: "110ms";
        readonly base: "240ms";
        readonly slow: "400ms";
        readonly easing: "cubic-bezier(0.2, 0, 0.38, 0.9)";
    };
};
export type Theme = typeof theme;
