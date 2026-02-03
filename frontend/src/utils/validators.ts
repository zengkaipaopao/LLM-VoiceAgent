/**
 * 验证工具函数
 */

/**
 * 验证电话号码格式(E.164)
 * @param phone - 电话号码
 * @returns 是否有效
 */
export function isValidPhone(phone: string): boolean {
  // E.164格式: +[国家代码][号码]
  const phoneRegex = /^\+?[1-9]\d{1,14}$/;
  return phoneRegex.test(phone);
}

/**
 * 验证邮箱格式
 * @param email - 邮箱地址
 * @returns 是否有效
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * 验证URL格式
 * @param url - URL字符串
 * @returns 是否有效
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * 验证UUID格式
 * @param uuid - UUID字符串
 * @returns 是否有效
 */
export function isValidUUID(uuid: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}

/**
 * 验证是否为空字符串
 * @param value - 字符串值
 * @returns 是否为空
 */
export function isEmpty(value: string | null | undefined): boolean {
  return !value || value.trim().length === 0;
}

/**
 * 验证字符串长度范围
 * @param value - 字符串值
 * @param min - 最小长度
 * @param max - 最大长度
 * @returns 是否在范围内
 */
export function isLengthInRange(
  value: string,
  min: number,
  max: number
): boolean {
  const length = value.trim().length;
  return length >= min && length <= max;
}
