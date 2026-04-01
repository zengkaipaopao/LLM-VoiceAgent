import { Call, Device } from '@twilio/voice-sdk';

import type { LogLevel } from '../testTabs/eventLog';
import type { CallState, DeviceState } from './types';
import { stringifyError } from './utils';

interface BindTwilioCallEventsOptions {
  setCallState: (value: CallState) => void;
  setIsDialing: (value: boolean) => void;
  setIsEnding: (value: boolean) => void;
  setIsMuted: (value: boolean) => void;
  setCallSid: (value: string) => void;
  setError: (value: string | null) => void;
  clearCallRef: () => void;
  pushLog: (level: LogLevel, message: string) => void;
}

interface BindTwilioDeviceEventsOptions {
  setDeviceState: (value: DeviceState) => void;
  setError: (value: string | null) => void;
  pushLog: (level: LogLevel, message: string) => void;
  tokenWillExpireMessage: string;
}

export function bindTwilioCallEvents(call: Call, options: BindTwilioCallEventsOptions): void {
  const {
    setCallState,
    setIsDialing,
    setIsEnding,
    setIsMuted,
    setCallSid,
    setError,
    clearCallRef,
    pushLog,
  } = options;

  call.on('ringing', () => {
    setCallState('ringing');
    pushLog('info', 'Call is ringing.');
  });

  call.on('accept', () => {
    setCallState('in_call');
    setIsDialing(false);
    setCallSid(call.parameters?.CallSid || '');
    pushLog('success', 'Call connected.');
  });

  call.on('disconnect', () => {
    setCallState('ended');
    setIsDialing(false);
    setIsEnding(false);
    setIsMuted(false);
    setCallSid(call.parameters?.CallSid || '');
    clearCallRef();
    pushLog('info', 'Call disconnected.');
  });

  call.on('cancel', () => {
    setCallState('ended');
    setIsDialing(false);
    setIsEnding(false);
    setIsMuted(false);
    clearCallRef();
    pushLog('warning', 'Call canceled.');
  });

  call.on('reject', () => {
    setCallState('ended');
    setIsDialing(false);
    setIsEnding(false);
    setIsMuted(false);
    clearCallRef();
    pushLog('warning', 'Call rejected.');
  });

  call.on('mute', (muted: boolean) => {
    setIsMuted(muted);
    pushLog('info', muted ? 'Microphone muted.' : 'Microphone unmuted.');
  });

  call.on('warning', (name: string) => {
    pushLog('warning', `Twilio warning: ${name}`);
  });

  call.on('warning-cleared', (name: string) => {
    pushLog('info', `Twilio warning cleared: ${name}`);
  });

  call.on('error', (callError: unknown) => {
    const message = stringifyError(callError);
    setCallState('error');
    setIsDialing(false);
    setIsEnding(false);
    setError(message);
    pushLog('error', `Call error: ${message}`);
  });
}

export function bindTwilioDeviceEvents(device: Device, options: BindTwilioDeviceEventsOptions): void {
  const { setDeviceState, setError, pushLog, tokenWillExpireMessage } = options;

  device.on('registering', () => {
    setDeviceState('registering');
    pushLog('info', 'Registering Twilio device...');
  });

  device.on('registered', () => {
    setDeviceState('registered');
    pushLog('success', 'Twilio device registered.');
  });

  device.on('unregistered', () => {
    setDeviceState('unregistered');
    pushLog('info', 'Twilio device unregistered.');
  });

  device.on('incoming', (incomingCall: Call) => {
    pushLog('warning', 'Incoming call received in test tab (auto-rejected).');
    incomingCall.reject();
  });

  device.on('tokenWillExpire', () => {
    pushLog('warning', tokenWillExpireMessage);
  });

  device.on('error', (deviceError: unknown) => {
    const message = stringifyError(deviceError);
    setDeviceState('error');
    setError(message);
    pushLog('error', `Device error: ${message}`);
  });
}
