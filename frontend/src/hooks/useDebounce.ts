// 示例: 防抖Hook
import { useEffect, useState } from 'react';

/**
 * useDebounce - 防抖Hook
 * 
 * 延迟更新值,避免频繁触发
 * 
 * @param value - 需要防抖的值
 * @param delay - 延迟时间(毫秒)
 * @returns 防抖后的值
 * 
 * @example
 * ```tsx
 * const [searchTerm, setSearchTerm] = useState('');
 * const debouncedSearch = useDebounce(searchTerm, 500);
 * 
 * useEffect(() => {
 *   // 只在用户停止输入500ms后执行搜索
 *   if (debouncedSearch) {
 *     searchAPI(debouncedSearch);
 *   }
 * }, [debouncedSearch]);
 * ```
 */
export function useDebounce<T>(value: T, delay: number = 500): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
