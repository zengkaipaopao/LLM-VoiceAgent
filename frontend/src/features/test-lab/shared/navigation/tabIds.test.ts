import { describe, expect, it } from 'vitest';

import { DEFAULT_TEST_TAB_ID, normalizeTestTabId } from './tabIds';

describe('normalizeTestTabId', () => {
  it('maps legacy text tabs to the unified text tab', () => {
    expect(normalizeTestTabId('simulation')).toBe('text');
    expect(normalizeTestTabId('chat')).toBe('text');
  });

  it('maps legacy voice tabs to the unified voice tab', () => {
    expect(normalizeTestTabId('twilio')).toBe('voice');
    expect(normalizeTestTabId('websocket')).toBe('voice');
    expect(normalizeTestTabId('live')).toBe('voice');
  });

  it('falls back to the default tab for empty values', () => {
    expect(normalizeTestTabId('')).toBe(DEFAULT_TEST_TAB_ID);
    expect(normalizeTestTabId(undefined)).toBe(DEFAULT_TEST_TAB_ID);
  });
});
