export const getTextDelta = (payload: unknown): string => {
  if (!payload || typeof payload !== 'object') {
    return '';
  }
  const candidate = payload as Record<string, unknown>;
  if (typeof candidate.delta === 'string') {
    return candidate.delta;
  }
  if (candidate.delta && typeof candidate.delta === 'object') {
    const deltaRecord = candidate.delta as Record<string, unknown>;
    if (typeof deltaRecord.text === 'string') {
      return deltaRecord.text;
    }
    if (Array.isArray(deltaRecord.content)) {
      return deltaRecord.content
        .map((item) => (typeof item === 'string' ? item : (item as Record<string, unknown>).text ?? ''))
        .join('');
    }
  }
  if (typeof candidate.text === 'string') {
    return candidate.text;
  }
  if (Array.isArray(candidate.delta)) {
    return candidate.delta.filter((chunk) => typeof chunk === 'string').join('');
  }
  if (Array.isArray(candidate.content)) {
    return candidate.content
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'text' in item && typeof item.text === 'string') {
          return item.text;
        }
        return '';
      })
      .join('');
  }
  return '';
};
