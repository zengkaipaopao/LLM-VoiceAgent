const INLINE_APPOINTMENT_JSON_REGEX = /\{[^{}]*"(?:operation|timestamp|caller_name|extra_request)"[\s\S]*?\}/g;
const SUPPRESSED_LINE_PATTERNS = [
  /内容を.*まとめ/,
  /記録を?(?:行|進)めさせていただきます/,
  /記録いたします/,
  /記録を行います/,
  /少々お待ちください/,
  /しばらくお待ち/,
];

export const sanitizeAssistantContent = (content: string): string => {
  // Remove completed fenced code blocks
  let sanitized = content.replace(/```[\s\S]*?```/g, '');
  // If the assistant is still streaming a block, drop everything from the first ``` onwards
  sanitized = sanitized.replace(/```[\s\S]*$/, '');
  const withoutInlineJson = sanitized.replace(INLINE_APPOINTMENT_JSON_REGEX, '');
  const withoutSystemHints = withoutInlineJson
    .split('\n')
    .map((line) => line.trim())
    .filter(
      (line) =>
        line &&
        !line.startsWith('※') &&
        !SUPPRESSED_LINE_PATTERNS.some((pattern) => pattern.test(line)),
    )
    .join('\n')
    .trim();
  return withoutSystemHints;
};
