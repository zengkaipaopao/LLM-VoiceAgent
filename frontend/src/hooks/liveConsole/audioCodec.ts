export const INPUT_TARGET_SAMPLE_RATE = 16000;
export const OUTPUT_DEFAULT_SAMPLE_RATE = 24000;

export function getAudioContextCtor(): typeof AudioContext | null {
  if (typeof window === 'undefined') return null;
  const ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  return ctor ?? null;
}

export function pcm16ToBase64(pcmBytes: Uint8Array): string {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < pcmBytes.length; i += chunkSize) {
    const chunk = pcmBytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export function base64ToBytes(encoded: string): Uint8Array {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function decodePcm16ToFloat32(bytes: Uint8Array): Float32Array {
  const sampleCount = Math.floor(bytes.length / 2);
  const floatSamples = new Float32Array(sampleCount);
  for (let i = 0; i < sampleCount; i += 1) {
    const lo = bytes[i * 2];
    const hi = bytes[i * 2 + 1];
    let sample = (hi << 8) | lo;
    if (sample >= 0x8000) sample -= 0x10000;
    floatSamples[i] = sample / 32768;
  }
  return floatSamples;
}

export function parsePcmSampleRate(mimeType: string | undefined, fallbackRate: number): number {
  if (!mimeType) return fallbackRate;
  const match = mimeType.toLowerCase().match(/rate=(\d{4,6})/);
  if (!match) return fallbackRate;
  const parsed = Number(match[1]);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallbackRate;
  return parsed;
}

export function resampleFloat32(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (!input.length) return input;
  if (!Number.isFinite(inputRate) || !Number.isFinite(outputRate)) return input;
  if (inputRate <= 0 || outputRate <= 0) return input;
  if (inputRate === outputRate) return input;

  const outputLength = Math.max(1, Math.round((input.length * outputRate) / inputRate));
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i += 1) {
    const sourceIndex = (i * inputRate) / outputRate;
    const lower = Math.floor(sourceIndex);
    const upper = Math.min(input.length - 1, lower + 1);
    const alpha = sourceIndex - lower;
    output[i] = input[lower] * (1 - alpha) + input[upper] * alpha;
  }
  return output;
}

export function float32ToPcm16Bytes(floatSamples: Float32Array): Uint8Array {
  const pcm16 = new Int16Array(floatSamples.length);
  for (let i = 0; i < floatSamples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatSamples[i]));
    pcm16[i] = sample < 0 ? sample * 32768 : sample * 32767;
  }
  return new Uint8Array(pcm16.buffer);
}
