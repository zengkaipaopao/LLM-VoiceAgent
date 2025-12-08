import { AppointmentRecordPayload } from '../../../api/appointments';

export type ParsedAppointment = {
  operation: 'create' | 'update' | 'delete';
  timestamp: string;
  callerName: string;
  company: string;
  appointment: string;
  category: string;
  amount: string;
  address: string;
  summary: string;
};

const JSON_BLOCK_REGEX = /```json\s*({[\s\S]+?})\s*```/i;

const normalizeOperation = (value?: string): ParsedAppointment['operation'] => {
  const normalized = (value ?? '').toLowerCase();
  if (normalized.includes('update') || normalized.includes('modify') || normalized.includes('変更')) {
    return 'update';
  }
  if (normalized.includes('delete') || normalized.includes('cancel') || normalized.includes('取消')) {
    return 'delete';
  }
  return 'create';
};

const pickString = (payload: Record<string, unknown>, candidates: string[], fallback = '') => {
  for (const key of candidates) {
    const value = payload[key];
    if (typeof value === 'string') {
      return value.trim();
    }
  }
  return fallback;
};

const extractJsonString = (text: string) => {
  const blockMatch = text.match(JSON_BLOCK_REGEX);
  if (blockMatch) return blockMatch[1];
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start !== -1 && end > start) {
    return text.slice(start, end + 1);
  }
  return null;
};

export const extractAppointmentFromText = (text: string): ParsedAppointment | null => {
  if (!text) return null;
  const jsonString = extractJsonString(text);
  if (!jsonString) return null;
  try {
    const parsed = JSON.parse(jsonString);
    return {
      operation: normalizeOperation(parsed.operation ?? parsed.action),
      timestamp: pickString(parsed, ['timestamp', 'time'], ''),
      callerName: pickString(parsed, ['caller_name', 'callerName', 'name'], '未提供'),
      company: pickString(parsed, ['company', 'company_name', 'companyName'], '未提供'),
      appointment: pickString(parsed, ['appointment', 'desired_time', 'desiredTime'], '未提供'),
      category: pickString(parsed, ['category', 'item'], '未提供'),
      amount: pickString(parsed, ['amount', 'quantity'], '未提供'),
      address: pickString(parsed, ['address', 'location'], '未提供'),
      summary: pickString(parsed, ['summary', 'note'], '未提供'),
    };
  } catch {
    return null;
  }
};

export type TranscriptEntry = {
  role: string;
  text: string;
  timestamp?: string;
};

export const buildRawTranscript = (entries: TranscriptEntry[]): string => {
  return entries
    .map((entry) => `[${entry.timestamp ?? '--'}][${entry.role}] ${entry.text}`)
    .join('\n');
};

export const composeAppointmentPayload = (
  parsed: ParsedAppointment,
  rawMessages: string,
): AppointmentRecordPayload => ({
  operation: parsed.operation,
  timestamp: parsed.timestamp,
  callerName: parsed.callerName,
  company: parsed.company,
  appointment: parsed.appointment,
  category: parsed.category,
  amount: parsed.amount,
  address: parsed.address,
  summary: parsed.summary,
  rawMessages,
});
