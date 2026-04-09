import { describe, expect, it } from 'vitest';

import { shouldAutoFinalizeByClosingPhrase } from './closingPhrase';

describe('shouldAutoFinalizeByClosingPhrase', () => {
  it('matches the expected japanese closing phrase pattern', () => {
    expect(
      shouldAutoFinalizeByClosingPhrase('依頼内容を承りました。ご利用ありがとうございます。')
    ).toBe(true);
  });

  it('ignores trailing questions even if the keywords appear', () => {
    expect(
      shouldAutoFinalizeByClosingPhrase('承りました。ご利用ありがとうございます？')
    ).toBe(false);
  });

  it('returns false when only one closing signal is present', () => {
    expect(shouldAutoFinalizeByClosingPhrase('ご利用ありがとうございます。')).toBe(false);
    expect(shouldAutoFinalizeByClosingPhrase('承りました。')).toBe(false);
  });
});
