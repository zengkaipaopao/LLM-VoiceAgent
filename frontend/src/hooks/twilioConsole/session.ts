import type { MutableRefObject } from 'react';
import type { Call, Device } from '@twilio/voice-sdk';

import { CallState, DeviceState } from './types';

interface ResetTwilioSessionOptions {
  callRef: MutableRefObject<Call | null>;
  deviceRef: MutableRefObject<Device | null>;
  setDeviceState: (value: DeviceState) => void;
  setCallState: (value: CallState) => void;
  setCallSid: (value: string) => void;
  setIsMuted: (value: boolean) => void;
}

const HANGUP_ELIGIBLE_CALL_STATES: CallState[] = ['dialing', 'ringing', 'in_call', 'ending'];

export function resetTwilioSession({
  callRef,
  deviceRef,
  setDeviceState,
  setCallState,
  setCallSid,
  setIsMuted,
}: ResetTwilioSessionOptions): void {
  try {
    callRef.current?.disconnect();
  } catch {
    // noop
  }
  callRef.current = null;

  try {
    deviceRef.current?.destroy();
  } catch {
    // noop
  }
  deviceRef.current = null;

  setDeviceState('idle');
  setCallState('idle');
  setCallSid('');
  setIsMuted(false);
}

export function canHangupCall(callRef: MutableRefObject<Call | null>, callState: CallState): boolean {
  return Boolean(callRef.current) && HANGUP_ELIGIBLE_CALL_STATES.includes(callState);
}
