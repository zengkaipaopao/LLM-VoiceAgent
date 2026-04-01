import type { CallState, DeviceState, TwilioStatusTagType } from './types';

export function stringifyError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  try {
    return JSON.stringify(error);
  } catch {
    return 'Unknown error';
  }
}

export function extractToken(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const data = payload as {
    token?: string;
    access_token?: string;
    accessToken?: string;
    data?: {
      token?: string;
      access_token?: string;
      accessToken?: string;
    };
  };
  return (
    data.token ||
    data.access_token ||
    data.accessToken ||
    data.data?.token ||
    data.data?.access_token ||
    data.data?.accessToken ||
    null
  );
}

export function resolveDeviceTagType(
  deviceState: DeviceState
): TwilioStatusTagType {
  if (deviceState === 'registered') return 'green';
  if (deviceState === 'registering') return 'teal';
  if (deviceState === 'error') return 'red';
  if (deviceState === 'unregistered') return 'warm-gray';
  return 'cool-gray';
}

export function resolveCallTagType(
  callState: CallState
): TwilioStatusTagType {
  if (callState === 'in_call') return 'green';
  if (callState === 'dialing' || callState === 'ringing' || callState === 'ending') return 'teal';
  if (callState === 'error') return 'red';
  if (callState === 'ended') return 'warm-gray';
  return 'cool-gray';
}
