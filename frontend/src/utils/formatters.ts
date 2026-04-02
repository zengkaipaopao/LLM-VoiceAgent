import i18n from '../config/i18n';

/**
 * 日期时间格式化工具
 */

function resolveLocale(locale?: string): string {
  if (locale && locale.trim().length > 0) {
    return locale;
  }

  if (i18n.resolvedLanguage) {
    return i18n.resolvedLanguage;
  }

  if (i18n.language) {
    return i18n.language;
  }

  if (typeof navigator !== 'undefined' && navigator.language) {
    return navigator.language;
  }

  return 'en-US';
}

function toDate(value: Date | string | number): Date {
  return typeof value === 'string' || typeof value === 'number' ? new Date(value) : value;
}

function isValidDate(value: Date): boolean {
  return !Number.isNaN(value.getTime());
}

interface DurationUnitConfig {
  hour: string;
  minute: string;
  second: string;
  separator: string;
}

const durationUnits: Record<string, DurationUnitConfig> = {
  'zh-CN': { hour: '小时', minute: '分', second: '秒', separator: '' },
  'ja-JP': { hour: '時間', minute: '分', second: '秒', separator: '' },
};

function resolveDurationUnits(locale: string): DurationUnitConfig {
  if (locale in durationUnits) {
    return durationUnits[locale];
  }

  const normalized = locale.toLowerCase();
  if (normalized.startsWith('zh')) {
    return durationUnits['zh-CN'];
  }
  if (normalized.startsWith('ja')) {
    return durationUnits['ja-JP'];
  }

  return { hour: 'h', minute: 'm', second: 's', separator: ' ' };
}

/**
 * 格式化日期为本地化字符串
 * @param date - 日期对象或时间戳
 * @param locale - 语言代码
 * @returns 格式化后的日期字符串
 */
export function formatDate(
  date: Date | string | number,
  locale?: string
): string {
  const dateObj = toDate(date);
  if (!isValidDate(dateObj)) {
    return String(date);
  }
  const resolvedLocale = resolveLocale(locale);
  
  return dateObj.toLocaleDateString(resolvedLocale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

/**
 * 格式化日期时间为本地化字符串
 * @param date - 日期对象或时间戳
 * @param locale - 语言代码
 * @returns 格式化后的日期时间字符串
 */
export function formatDateTime(
  date: Date | string | number,
  locale?: string
): string {
  const dateObj = toDate(date);
  if (!isValidDate(dateObj)) {
    return String(date);
  }
  const resolvedLocale = resolveLocale(locale);
  
  return dateObj.toLocaleString(resolvedLocale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * 格式化时长(秒)为可读字符串
 * @param seconds - 秒数
 * @param locale - 语言代码
 * @returns 格式化后的时长字符串,如 "2分30秒"
 */
export function formatDuration(seconds: number, locale?: string): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const secs = Math.floor(safeSeconds % 60);
  const resolvedLocale = resolveLocale(locale);
  const units = resolveDurationUnits(resolvedLocale);
  
  const parts: string[] = [];
  
  if (hours > 0) {
    parts.push(`${hours}${units.hour}`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}${units.minute}`);
  }
  if (secs > 0 || parts.length === 0) {
    parts.push(`${secs}${units.second}`);
  }
  
  return parts.join(units.separator);
}

/**
 * 格式化相对时间
 * @param date - 日期对象或时间戳
 * @param locale - 语言代码
 * @returns 相对时间字符串,如 "3分钟前"
 */
export function formatRelativeTime(date: Date | string | number, locale?: string): string {
  const dateObj = toDate(date);
  if (!isValidDate(dateObj)) {
    return String(date);
  }
  const resolvedLocale = resolveLocale(locale);
  
  const now = new Date();
  const diffMs = now.getTime() - dateObj.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const absSecs = Math.abs(diffSecs);
  const rtf = new Intl.RelativeTimeFormat(resolvedLocale, { numeric: 'auto' });
  
  if (absSecs < 60) {
    return rtf.format(-diffSecs, 'second');
  }

  const diffMins = Math.floor(diffSecs / 60);
  const absMins = Math.abs(diffMins);
  if (absMins < 60) {
    return rtf.format(-diffMins, 'minute');
  }

  const diffHours = Math.floor(diffMins / 60);
  const absHours = Math.abs(diffHours);
  if (absHours < 24) {
    return rtf.format(-diffHours, 'hour');
  }

  const diffDays = Math.floor(diffHours / 24);
  if (Math.abs(diffDays) < 7) {
    return rtf.format(-diffDays, 'day');
  }

  return formatDate(dateObj, resolvedLocale);
}

/**
 * 格式化为日语标准日期格式 (e.g. 2025年8月20日（水）09:00:00)
 */
export function formatJapaneseDate(dateString: string | Date): string {
  if (!dateString) return '-';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return String(dateString);

  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const weekday = weekdays[date.getDay()];
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');

  return `${year}年${month}月${day}日（${weekday}）${hours}:${minutes}:${seconds}`;
}

/**
 * 格式化为标准调用时间 (e.g. 2025/08/20 09:00:00)
 */
export function formatCallTime(dateString: string | Date): string {
  if (!dateString) return '-';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return String(dateString);

  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');

  return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
}
