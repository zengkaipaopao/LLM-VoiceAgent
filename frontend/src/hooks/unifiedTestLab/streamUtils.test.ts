import { describe, expect, it } from 'vitest';

import { sanitizeAssistantPrefix } from './streamUtils';

describe('sanitizeAssistantPrefix', () => {
  it('removes inline assistant role labels', () => {
    const raw =
      'いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。\n\nAssistant: 2026年4月1日の粗大ゴミ回収のご希望ですね。';

    const sanitized = sanitizeAssistantPrefix(raw);

    expect(sanitized).not.toContain('Assistant:');
    expect(sanitized).toContain('2026年4月1日の粗大ゴミ回収のご希望ですね。');
  });

  it('truncates injected user turns', () => {
    const raw = '承知しました。\n\nUser: はい\nAssistant: ありがとうございます。';

    const sanitized = sanitizeAssistantPrefix(raw);

    expect(sanitized).toBe('承知しました。');
  });
});
