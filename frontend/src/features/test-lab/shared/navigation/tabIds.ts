const LEGACY_TEST_TAB_ID_MAP: Record<string, string> = {
  simulation: 'text',
  chat: 'text',
  twilio: 'voice',
  websocket: 'voice',
  live: 'voice',
};

export const DEFAULT_TEST_TAB_ID = 'text';

export function normalizeTestTabId(tab: string | null | undefined): string {
  const raw = (tab || '').trim().toLowerCase();
  if (!raw) {
    return DEFAULT_TEST_TAB_ID;
  }

  return LEGACY_TEST_TAB_ID_MAP[raw] || raw;
}
