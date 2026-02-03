import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';

/**
 * i18n配置 - 模块化翻译文件结构
 * 
 * 翻译文件按命名空间组织:
 * - common: 通用文本(按钮、状态等)
 * - pages: 页面特定文本
 * - navigation: 导航菜单文本
 * 
 * 优势:
 * - 按需懒加载,提升性能
 * - 文件小,易于维护
 * - 多人协作不冲突
 */
i18n
  // 使用HTTP后端懒加载翻译文件
  .use(HttpBackend)
  // 检测用户语言
  .use(LanguageDetector)
  // 传递i18n实例给react-i18next
  .use(initReactI18next)
  // 初始化i18next
  .init({
    // 默认语言
    fallbackLng: 'zh-CN',
    
    // 支持的语言
    supportedLngs: ['zh-CN', 'en-US', 'ja-JP'],
    
    // 命名空间配置
    ns: ['common', 'pages', 'navigation'], // 所有命名空间
    defaultNS: 'common', // 默认命名空间
    
    // 开发环境显示调试信息
    debug: false,
    
    // React已经处理了XSS
    interpolation: {
      escapeValue: false,
    },

    // 语言检测配置
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },

    // HTTP后端配置
    backend: {
      // 翻译文件路径模板
      loadPath: '/locales/{{lng}}/{{ns}}.json',
      
      // 请求超时
      requestOptions: {
        mode: 'cors',
        credentials: 'same-origin',
        cache: 'default',
      },
    },

    // 在开发环境记录缺失的翻译key
    saveMissing: import.meta.env.DEV,
    missingKeyHandler: (lng, ns, key) => {
      if (import.meta.env.DEV) {
        console.warn(`[i18n] Missing translation: ${ns}:${key} (${lng})`);
      }
    },
  });

export default i18n;
