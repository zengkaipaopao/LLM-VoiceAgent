/**
 * 日期时间格式化工具
 */

/**
 * 格式化日期为本地化字符串
 * @param date - 日期对象或时间戳
 * @param locale - 语言代码,默认为中文
 * @returns 格式化后的日期字符串
 */
export function formatDate(
  date: Date | string | number,
  locale: string = 'zh-CN'
): string {
  const dateObj = typeof date === 'string' || typeof date === 'number' 
    ? new Date(date) 
    : date;
  
  return dateObj.toLocaleDateString(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

/**
 * 格式化日期时间为本地化字符串
 * @param date - 日期对象或时间戳
 * @param locale - 语言代码,默认为中文
 * @returns 格式化后的日期时间字符串
 */
export function formatDateTime(
  date: Date | string | number,
  locale: string = 'zh-CN'
): string {
  const dateObj = typeof date === 'string' || typeof date === 'number' 
    ? new Date(date) 
    : date;
  
  return dateObj.toLocaleString(locale, {
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
 * @returns 格式化后的时长字符串,如 "2分30秒"
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  const parts: string[] = [];
  
  if (hours > 0) {
    parts.push(`${hours}小时`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}分`);
  }
  if (secs > 0 || parts.length === 0) {
    parts.push(`${secs}秒`);
  }
  
  return parts.join('');
}

/**
 * 格式化相对时间
 * @param date - 日期对象或时间戳
 * @returns 相对时间字符串,如 "3分钟前"
 */
export function formatRelativeTime(date: Date | string | number): string {
  const dateObj = typeof date === 'string' || typeof date === 'number' 
    ? new Date(date) 
    : date;
  
  const now = new Date();
  const diffMs = now.getTime() - dateObj.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffSecs < 60) {
    return '刚刚';
  } else if (diffMins < 60) {
    return `${diffMins}分钟前`;
  } else if (diffHours < 24) {
    return `${diffHours}小时前`;
  } else if (diffDays < 7) {
    return `${diffDays}天前`;
  } else {
    return formatDate(dateObj);
  }
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
