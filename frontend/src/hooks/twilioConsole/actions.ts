import { Call, Device } from '@twilio/voice-sdk';

import { extractToken } from './utils';

interface FetchTokenFromEndpointOptions {
  endpointBase: string;
  identity: string;
}

interface ConnectTwilioCallOptions {
  device: Device;
  toNumber: string;
  identity: string;
  promptCode?: string;
}

export async function fetchTokenFromEndpoint({
  endpointBase,
  identity,
}: FetchTokenFromEndpointOptions): Promise<string> {
  const connector = endpointBase.includes('?') ? '&' : '?';
  const url = `${endpointBase}${connector}identity=${encodeURIComponent(identity)}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Token endpoint returned ${response.status}`);
  }

  const payload = await response.json();
  const token = extractToken(payload);
  if (!token) {
    throw new Error('No token field found in endpoint response');
  }

  return token;
}

export async function registerTwilioDevice(token: string): Promise<Device> {
  const device = new Device(token, {
    logLevel: 1,
    closeProtection: false,
  });

  await device.register();
  return device;
}

export async function connectTwilioCall({
  device,
  toNumber,
  identity,
  promptCode,
}: ConnectTwilioCallOptions): Promise<Call> {
  const params: Record<string, string> = {
    To: toNumber,
    identity,
  };

  if (promptCode) {
    params.prompt_code = promptCode;
  }

  return device.connect({ params });
}
