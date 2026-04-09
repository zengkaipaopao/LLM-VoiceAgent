export function shouldAutoFinalizeByClosingPhrase(content: string): boolean {
  if (!content) {
    return false;
  }

  const normalized = content.replace(/\s+/g, '');
  const tail = normalized.slice(-80);
  const hasThanks = tail.includes('ご利用ありがとうございます');
  const hasAccepted = tail.includes('承りました') || tail.includes('承知いたしました');
  if (/[?？]$/.test(tail)) {
    return false;
  }
  return hasThanks && hasAccepted;
}
