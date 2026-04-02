import { describe, expect, it } from 'vitest';

import {
  formatCallTime,
  formatDuration,
  formatJapaneseDate,
} from './formatters';

describe('formatters', () => {
  it('formats duration into Chinese human-readable text', () => {
    expect(formatDuration(0, 'zh-CN')).toBe('0秒');
    expect(formatDuration(65, 'zh-CN')).toBe('1分5秒');
    expect(formatDuration(3661, 'zh-CN')).toBe('1小时1分1秒');
  });

  it('formats duration with english units', () => {
    expect(formatDuration(65, 'en-US')).toBe('1m 5s');
    expect(formatDuration(3661, 'en-US')).toBe('1h 1m 1s');
  });

  it('formats call time with zero-padded values', () => {
    const date = new Date(2026, 0, 2, 3, 4, 5);
    expect(formatCallTime(date)).toBe('2026/01/02 03:04:05');
  });

  it('formats Japanese date string with weekday', () => {
    const date = new Date(2026, 0, 2, 3, 4, 5);
    expect(formatJapaneseDate(date)).toBe('2026年1月2日（金）03:04:05');
  });
});
