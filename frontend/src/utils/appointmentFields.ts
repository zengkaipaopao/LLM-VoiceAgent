const EMPTY_TEXT_MARKERS = new Set(['', '-', '--', '—', 'N/A', 'n/a', 'null', 'undefined']);

const AMOUNT_PATTERN =
  /([0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:kg|ｋｇ|キロ(?:グラム)?|g|ｇ|グラム|トン|ton(?:s)?|t(?![0-9０-９])|吨|噸|m[3３]|m³|㎥|立方メートル|立方米|立方|立米|袋|点|個|台|脚|本|箱|枚))/i;

const NUMERIC_PATTERN = /^[0-9０-９]+(?:[.,．][0-9０-９]+)?$/;

function normalizeText(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  if (!text) return null;
  return EMPTY_TEXT_MARKERS.has(text) ? null : text;
}

export function extractAmountFromText(value: unknown): string | null {
  const text = normalizeText(value);
  if (!text) return null;
  const match = text.match(AMOUNT_PATTERN);
  return match ? match[1].trim() : null;
}

function formatWithUnit(value: string, unit: 'kg' | 'm3'): string {
  return NUMERIC_PATTERN.test(value) ? `${value} ${unit}` : value;
}

function extractAmountFromRawMessages(value: unknown, depth = 0): string | null {
  if (depth > 4 || value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return extractAmountFromText(value);
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const found = extractAmountFromRawMessages(item, depth + 1);
      if (found) return found;
    }
    return null;
  }

  if (typeof value !== 'object') {
    return null;
  }

  const record = value as Record<string, unknown>;
  const preferredKeys = [
    'amount',
    'quantity',
    'volume',
    'weight',
    'estimated_weight_kg',
    'estimated_volume_m3',
    'content',
    'text',
    'summary',
    'appointment_content',
    'special_notes',
    'transcript',
    'conversation',
    'messages',
  ];

  for (const key of preferredKeys) {
    if (!(key in record)) continue;
    const found = extractAmountFromRawMessages(record[key], depth + 1);
    if (found) return found;
  }

  for (const candidate of Object.values(record)) {
    const found = extractAmountFromRawMessages(candidate, depth + 1);
    if (found) return found;
  }

  return null;
}

export function resolveAppointmentAmount(params: {
  amount?: unknown;
  extractedData?: Record<string, unknown> | null;
  summary?: unknown;
  appointmentContent?: unknown;
  rawMessages?: unknown;
}): string {
  const { amount, extractedData, summary, appointmentContent, rawMessages } = params;
  const extracted = extractedData || {};

  const directAmount = normalizeText(amount);
  if (directAmount) return directAmount;

  const extractedDirect = normalizeText(
    extracted.amount ?? extracted.quantity ?? extracted.volume ?? extracted.weight
  );
  if (extractedDirect) return extractedDirect;

  const estimatedWeight = extracted.estimated_weight_kg;
  if (typeof estimatedWeight === 'number' && Number.isFinite(estimatedWeight)) {
    return `${estimatedWeight} kg`;
  }
  const estimatedWeightText = normalizeText(extracted.weight_kg);
  if (estimatedWeightText) {
    return formatWithUnit(estimatedWeightText, 'kg');
  }
  const estimatedWeightText2 = normalizeText(extracted.estimated_weight_kg);
  if (estimatedWeightText2) {
    return formatWithUnit(estimatedWeightText2, 'kg');
  }

  const estimatedVolume = extracted.estimated_volume_m3;
  if (typeof estimatedVolume === 'number' && Number.isFinite(estimatedVolume)) {
    return `${estimatedVolume} m3`;
  }
  const estimatedVolumeText = normalizeText(estimatedVolume);
  if (estimatedVolumeText) {
    return formatWithUnit(estimatedVolumeText, 'm3');
  }

  const fromText =
    extractAmountFromText(summary) ||
    extractAmountFromText(appointmentContent) ||
    extractAmountFromText(extracted.summary) ||
    extractAmountFromText(extracted.appointment_content) ||
    extractAmountFromText(extracted.special_notes) ||
    extractAmountFromRawMessages(rawMessages) ||
    extractAmountFromRawMessages(extracted.conversation) ||
    extractAmountFromRawMessages(extracted.messages) ||
    extractAmountFromRawMessages(extracted.transcript);
  if (fromText) return fromText;

  return '-';
}
