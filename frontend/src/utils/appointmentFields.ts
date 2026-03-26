const EMPTY_TEXT_MARKERS = new Set(['', '-', '--', '—', 'N/A', 'n/a', 'null', 'undefined']);

const AMOUNT_PATTERN =
  /([0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:kg|ｋｇ|キロ(?:グラム)?|g|ｇ|グラム|トン|ton(?:s)?|m[3３]|m³|㎥|立方メートル|立米|袋|点|個|台|脚|本|箱|枚))/i;

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

export function resolveAppointmentAmount(params: {
  amount?: unknown;
  extractedData?: Record<string, unknown> | null;
  summary?: unknown;
  appointmentContent?: unknown;
}): string {
  const { amount, extractedData, summary, appointmentContent } = params;
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
    if (/^[0-9０-９]+(?:[.,．][0-9０-９]+)?$/.test(estimatedWeightText)) {
      return `${estimatedWeightText} kg`;
    }
    return estimatedWeightText;
  }

  const estimatedVolume = extracted.estimated_volume_m3;
  if (typeof estimatedVolume === 'number' && Number.isFinite(estimatedVolume)) {
    return `${estimatedVolume} m3`;
  }
  const estimatedVolumeText = normalizeText(estimatedVolume);
  if (estimatedVolumeText) {
    return `${estimatedVolumeText} m3`;
  }

  const fromText =
    extractAmountFromText(summary) ||
    extractAmountFromText(appointmentContent) ||
    extractAmountFromText(extracted.summary) ||
    extractAmountFromText(extracted.appointment_content) ||
    extractAmountFromText(extracted.special_notes);
  if (fromText) return fromText;

  return '-';
}
