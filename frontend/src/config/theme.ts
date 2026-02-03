/**
 * Carbon Design System 主题配置
 * 
 * 此文件定义了应用的主题配置,包括颜色、间距、字体等设计令牌
 * 遵循 Carbon Design System 的设计规范
 */

// Carbon Design System 主题
export const theme = {
  // 颜色系统 - 使用 Carbon Design Tokens
  colors: {
    // 主要颜色
    primary: 'var(--cds-interactive-01, #0f62fe)',
    primaryHover: 'var(--cds-interactive-01-hover, #0353e9)',
    
    // 背景颜色
    background: 'var(--cds-ui-background, #ffffff)',
    backgroundAlt: 'var(--cds-ui-01, #f4f4f4)',
    
    // 文本颜色
    textPrimary: 'var(--cds-text-01, #161616)',
    textSecondary: 'var(--cds-text-02, #525252)',
    textPlaceholder: 'var(--cds-text-03, #a8a8a8)',
    
    // 边框颜色
    border: 'var(--cds-ui-03, #e0e0e0)',
    borderSubtle: 'var(--cds-border-subtle, #e0e0e0)',
    
    // 状态颜色
    success: 'var(--cds-support-02, #24a148)',
    warning: 'var(--cds-support-03, #f1c21b)',
    error: 'var(--cds-support-01, #da1e28)',
    info: 'var(--cds-support-04, #0043ce)',
  },
  
  // 间距系统 - Carbon 使用 8px 基础单位
  spacing: {
    xs: '0.25rem',  // 4px
    sm: '0.5rem',   // 8px
    md: '1rem',     // 16px
    lg: '1.5rem',   // 24px
    xl: '2rem',     // 32px
    xxl: '3rem',    // 48px
  },
  
  // 字体系统
  typography: {
    fontFamily: "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
    fontSize: {
      xs: '0.75rem',    // 12px
      sm: '0.875rem',   // 14px
      base: '1rem',     // 16px
      lg: '1.125rem',   // 18px
      xl: '1.25rem',    // 20px
      '2xl': '1.5rem',  // 24px
      '3xl': '2rem',    // 32px
    },
    fontWeight: {
      regular: 400,
      medium: 500,
      semibold: 600,
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75,
    },
  },
  
  // 断点系统 - Carbon Design 响应式断点
  breakpoints: {
    sm: '320px',   // 小屏幕
    md: '672px',   // 中等屏幕
    lg: '1056px',  // 大屏幕
    xl: '1312px',  // 超大屏幕
    max: '1584px', // 最大宽度
  },
  
  // 阴影系统
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 2px 6px 0 rgba(0, 0, 0, 0.1)',
    lg: '0 4px 12px 0 rgba(0, 0, 0, 0.15)',
  },
  
  // 圆角系统
  borderRadius: {
    none: '0',
    sm: '0.125rem',  // 2px
    md: '0.25rem',   // 4px
    lg: '0.5rem',    // 8px
    full: '9999px',
  },
  
  // 过渡动画
  transitions: {
    fast: '110ms',
    base: '240ms',
    slow: '400ms',
    easing: 'cubic-bezier(0.2, 0, 0.38, 0.9)',
  },
} as const;

export type Theme = typeof theme;
