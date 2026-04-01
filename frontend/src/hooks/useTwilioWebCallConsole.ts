import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Call, Device } from '@twilio/voice-sdk';

import { API_BASE_URL } from '../api/http';
import { appendEventLog, EventLog, LogLevel } from './testTabs/eventLog';
import { connectTwilioCall, fetchTokenFromEndpoint, registerTwilioDevice } from './twilioConsole/actions';
import { CallState, DeviceState, TwilioStatusTagType } from './twilioConsole/types';
import { bindTwilioCallEvents, bindTwilioDeviceEvents } from './twilioConsole/eventBinders';
import { canHangupCall, resetTwilioSession } from './twilioConsole/session';
import { resolveCallTagType, resolveDeviceTagType, stringifyError } from './twilioConsole/utils';
import { UseTwilioWebCallConsoleResult } from './twilioConsole/hookTypes';
import { usePromptTemplates } from './usePromptTemplates';

export type { CallState, DeviceState, TwilioStatusTagType } from './twilioConsole/types';
export type { EventLog, LogLevel } from './testTabs/eventLog';

export function useTwilioWebCallConsole(): UseTwilioWebCallConsoleResult {
  const { t } = useTranslation(['pages']);

  const [identity, setIdentity] = useState('webcall-tester');
  const [toNumber, setToNumber] = useState('+819012345678');
  const [tokenEndpoint, setTokenEndpoint] = useState(`${API_BASE_URL}/twilio/token`);
  const [useEndpoint, setUseEndpoint] = useState(true);
  const [accessToken, setAccessToken] = useState('');

  const [deviceState, setDeviceState] = useState<DeviceState>('idle');
  const [callState, setCallState] = useState<CallState>('idle');
  const [callSid, setCallSid] = useState<string>('');
  const [isMuted, setIsMuted] = useState(false);

  const [logs, setLogs] = useState<EventLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [isFetchingToken, setIsFetchingToken] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isDialing, setIsDialing] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  const deviceRef = useRef<Device | null>(null);
  const callRef = useRef<Call | null>(null);

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((prev) => appendEventLog(prev, level, message, 120));
  }, []);

  const handlePromptLoadError = useCallback(
    (loadError: unknown) => {
      pushLog('error', `Prompt list load failed: ${stringifyError(loadError)}`);
    },
    [pushLog]
  );

  const { prompts, loadingPrompts, selectedPromptCode, setSelectedPromptCode, selectedPrompt } =
    usePromptTemplates({
      preferredCode: 'base_appointment',
      onError: handlePromptLoadError,
    });

  const clearAlerts = useCallback(() => {
    setError(null);
    setInfo(null);
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const clearCallRef = useCallback(() => {
    callRef.current = null;
  }, []);

  const resetSession = useCallback(() => {
    resetTwilioSession({
      callRef,
      deviceRef,
      setDeviceState,
      setCallState,
      setCallSid,
      setIsMuted,
    });
  }, [callRef, deviceRef]);

  useEffect(() => {
    return () => {
      resetSession();
    };
  }, [resetSession]);

  const fetchToken = useCallback(async () => {
    if (!useEndpoint) return;
    setIsFetchingToken(true);
    clearAlerts();
    try {
      const base = tokenEndpoint.trim() || `${API_BASE_URL}/twilio/token`;
      const token = await fetchTokenFromEndpoint({
        endpointBase: base,
        identity: identity.trim() || 'webcall-tester',
      });
      setAccessToken(token);
      setInfo(t('pages:test.twilio.info.tokenFetched', 'Twilio token fetched successfully.'));
      pushLog('success', 'Access token fetched from endpoint.');
    } catch (fetchError) {
      const message = stringifyError(fetchError);
      setError(message);
      pushLog('error', `Fetch token failed: ${message}`);
    } finally {
      setIsFetchingToken(false);
    }
  }, [clearAlerts, identity, pushLog, t, tokenEndpoint, useEndpoint]);

  const bindCallEvents = useCallback(
    (call: Call) => {
      bindTwilioCallEvents(call, {
        setCallState,
        setIsDialing,
        setIsEnding,
        setIsMuted,
        setCallSid,
        setError,
        clearCallRef,
        pushLog,
      });
    },
    [clearCallRef, pushLog]
  );

  const initializeDevice = useCallback(async () => {
    clearAlerts();
    const token = accessToken.trim();
    if (!token) {
      setError(t('pages:test.twilio.errors.noToken', 'Please provide a Twilio Access Token first.'));
      return;
    }

    setIsInitializing(true);
    try {
      resetSession();
      const device = await registerTwilioDevice(token);
      deviceRef.current = device;
      bindTwilioDeviceEvents(device, {
        setDeviceState,
        setError,
        pushLog,
        tokenWillExpireMessage: t(
          'pages:test.twilio.logs.tokenWillExpire',
          'Access token will expire soon. Refresh token to avoid call interruption.'
        ),
      });

      setInfo(t('pages:test.twilio.info.deviceReady', 'Twilio device is ready.'));
    } catch (initError) {
      const message = stringifyError(initError);
      setDeviceState('error');
      setError(message);
      pushLog('error', `Initialize device failed: ${message}`);
    } finally {
      setIsInitializing(false);
    }
  }, [accessToken, clearAlerts, pushLog, resetSession, t]);

  const handleDial = useCallback(async () => {
    clearAlerts();
    const device = deviceRef.current;
    if (!device || deviceState !== 'registered') {
      setError(t('pages:test.twilio.errors.deviceNotReady', 'Please initialize and register device first.'));
      return;
    }
    if (!toNumber.trim()) {
      setError(t('pages:test.twilio.errors.noTarget', 'Please enter a target phone number.'));
      return;
    }
    if (callRef.current) {
      setError(t('pages:test.twilio.errors.callAlreadyActive', 'A call is already active.'));
      return;
    }

    setIsDialing(true);
    setCallState('dialing');
    pushLog('info', `Dialing ${toNumber.trim()} ...`);

    try {
      const call = await connectTwilioCall({
        device,
        toNumber: toNumber.trim(),
        identity: identity.trim() || 'webcall-tester',
        promptCode: selectedPromptCode || undefined,
      });
      callRef.current = call;
      bindCallEvents(call);
      setCallSid(call.parameters?.CallSid || '');
    } catch (dialError) {
      const message = stringifyError(dialError);
      setCallState('error');
      setIsDialing(false);
      setError(message);
      pushLog('error', `Dial failed: ${message}`);
    }
  }, [bindCallEvents, clearAlerts, deviceState, identity, pushLog, selectedPromptCode, t, toNumber]);

  const handleHangUp = useCallback(() => {
    clearAlerts();
    const call = callRef.current;
    if (!call) return;

    try {
      setIsEnding(true);
      setCallState('ending');
      call.disconnect();
      pushLog('info', 'Disconnect requested.');
    } catch (endError) {
      const message = stringifyError(endError);
      setIsEnding(false);
      setCallState('error');
      setError(message);
      pushLog('error', `Disconnect failed: ${message}`);
    }
  }, [clearAlerts, pushLog]);

  const handleToggleMute = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    call.mute(!isMuted);
  }, [isMuted]);

  const handleUnregister = useCallback(async () => {
    const device = deviceRef.current;
    if (!device) return;
    clearAlerts();
    try {
      await device.unregister();
      setDeviceState('unregistered');
      pushLog('info', 'Device unregistered.');
    } catch (unregisterError) {
      const message = stringifyError(unregisterError);
      setError(message);
      pushLog('error', `Unregister failed: ${message}`);
    }
  }, [clearAlerts, pushLog]);

  const activePrompt = selectedPrompt;
  const canMute = callState === 'in_call';
  const canHangup = canHangupCall(callRef, callState);

  const deviceTagType = useMemo(() => resolveDeviceTagType(deviceState), [deviceState]);
  const callTagType = useMemo(() => resolveCallTagType(callState), [callState]);

  return {
    prompts,
    loadingPrompts,
    selectedPromptCode,
    setSelectedPromptCode,
    identity,
    setIdentity,
    toNumber,
    setToNumber,
    tokenEndpoint,
    setTokenEndpoint,
    useEndpoint,
    setUseEndpoint,
    accessToken,
    setAccessToken,
    deviceState,
    callState,
    callSid,
    isMuted,
    logs,
    error,
    setError,
    info,
    setInfo,
    isFetchingToken,
    isInitializing,
    isDialing,
    isEnding,
    activePrompt,
    canMute,
    canHangup,
    deviceTagType,
    callTagType,
    clearLogs,
    resetSession,
    fetchToken,
    initializeDevice,
    handleDial,
    handleHangUp,
    handleToggleMute,
    handleUnregister,
  };
}
