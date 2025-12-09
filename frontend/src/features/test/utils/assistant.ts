const INLINE_APPOINTMENT_JSON_REGEX = /\{[^{}]*"(?:operation|timestamp|caller_name|extra_request)"[\s\S]*?\}/g;

export const sanitizeAssistantContent = (content: string): string => {
  const withoutCodeBlocks = content.replace(/```[\s\S]*?```/g, '');
  const withoutInlineJson = withoutCodeBlocks.replace(INLINE_APPOINTMENT_JSON_REGEX, '');
  const withoutSystemHints = withoutInlineJson
    .split('\n')
    .filter((line) => line && !line.trim().startsWith('※'))
    .join('\n')
    .trim();
  return withoutSystemHints;
};
