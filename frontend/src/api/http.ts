import axios, { AxiosError, AxiosHeaders, AxiosResponse } from 'axios';
import { z } from 'zod';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const APP_API_KEY = (import.meta.env.VITE_APP_API_KEY ?? '').trim();

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
});

const ApiErrorPayloadSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.unknown().optional(),
});

const ApiEnvelopeSchema = z.object({
  success: z.boolean(),
  data: z.unknown().optional(),
  meta: z.unknown().optional(),
  error: ApiErrorPayloadSchema.nullable().optional(),
  message: z.string().nullable().optional(),
});

export class ApiError extends Error {
  code: string;
  status?: number;
  details?: unknown;

  constructor(code: string, message: string, status?: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function buildApiRequestHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  if (APP_API_KEY && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${APP_API_KEY}`);
  }
  return headers;
}

const parseEnvelopeOrThrow = (response: AxiosResponse): AxiosResponse => {
  const parsed = ApiEnvelopeSchema.safeParse(response.data);
  if (!parsed.success) {
    throw new ApiError(
      'INVALID_API_ENVELOPE',
      'Invalid API response envelope.',
      response.status,
      parsed.error.issues
    );
  }

  if (!parsed.data.success) {
    const envelopeError = parsed.data.error;
    throw new ApiError(
      envelopeError?.code ?? 'API_REQUEST_FAILED',
      envelopeError?.message ?? parsed.data.message ?? 'Request failed.',
      response.status,
      envelopeError?.details
    );
  }

  return response;
};

const toApiError = (error: AxiosError): ApiError => {
  const status = error.response?.status;
  const parsed = ApiEnvelopeSchema.safeParse(error.response?.data);

  if (parsed.success) {
    const envelopeError = parsed.data.error;
    return new ApiError(
      envelopeError?.code ?? `HTTP_${status ?? 0}`,
      envelopeError?.message ?? parsed.data.message ?? error.message,
      status,
      envelopeError?.details
    );
  }

  return new ApiError('NETWORK_ERROR', error.message || 'Network error', status);
};

if (APP_API_KEY) {
  http.interceptors.request.use((config) => {
    const headers = AxiosHeaders.from(config.headers ?? {});
    if (!headers.get('Authorization')) {
      headers.set('Authorization', `Bearer ${APP_API_KEY}`);
    }
    config.headers = headers;
    return config;
  });
}

http.interceptors.response.use(
  (response) => parseEnvelopeOrThrow(response),
  (error: unknown) => {
    if (error instanceof ApiError) {
      return Promise.reject(error);
    }
    if (axios.isAxiosError(error)) {
      return Promise.reject(toApiError(error));
    }
    const message = error instanceof Error ? error.message : 'Unknown request error';
    return Promise.reject(new ApiError('UNKNOWN_ERROR', message));
  }
);
