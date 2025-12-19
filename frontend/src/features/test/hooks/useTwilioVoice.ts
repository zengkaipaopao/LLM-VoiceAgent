import { useCallback, useEffect, useReducer, useRef } from 'react';
import { Call, Device } from '@twilio/voice-sdk';

type CallLog = {
  timestamp: string;
  message: string;
};

type TwilioVoiceStatus = 'idle' | 'ready' | 'error' | 'calling';

type TwilioVoiceState = {
  identity: string;
  dialNumber: string;
  status: TwilioVoiceStatus;
  loading: boolean;
  error: string | null;
  logs: CallLog[];
};

type Action =
  | { type: 'set'; payload: Partial<TwilioVoiceState> }
  | { type: 'append_log'; log: CallLog };

const DEFAULT_TWILIO_NUMBER = import.meta.env.VITE_TWILIO_DEFAULT_NUMBER ?? '+17753689279';

const initialState: TwilioVoiceState = {
  identity: '',
  dialNumber: '',
  status: 'idle',
  loading: false,
  error: null,
  logs: [],
};

const reducer = (state: TwilioVoiceState, action: Action): TwilioVoiceState => {
  switch (action.type) {
    case 'set':
      return { ...state, ...action.payload };
    case 'append_log':
      return { ...state, logs: [...state.logs, action.log] };
    default:
      return state;
  }
};

type UseTwilioVoiceParams = {
  promptId?: string;
};

export type TwilioVoiceApi = {
  identity: string;
  setIdentity: (value: string) => void;
  dialNumber: string;
  setDialNumber: (value: string) => void;
  status: TwilioVoiceStatus;
  loading: boolean;
  error: string | null;
  logs: CallLog[];
  initializeDevice: () => Promise<void>;
  startCall: () => Promise<void>;
  hangup: () => void;
  clearError: () => void;
};

export function useTwilioVoice({ promptId }: UseTwilioVoiceParams): TwilioVoiceApi {
  const [state, dispatch] = useReducer(reducer, initialState);
  const deviceRef = useRef<Device | null>(null);
  const activeCallRef = useRef<Call | null>(null);

  const appendLog = useCallback((message: string) => {
    dispatch({
      type: 'append_log',
      log: { timestamp: new Date().toLocaleTimeString(), message },
    });
  }, []);

  const setIdentity = useCallback((value: string) => {
    dispatch({ type: 'set', payload: { identity: value } });
  }, []);

  const setDialNumber = useCallback((value: string) => {
    dispatch({ type: 'set', payload: { dialNumber: value } });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'set', payload: { error: null } });
  }, []);

  const initializeDevice = useCallback(async () => {
    if (state.loading) return;
    dispatch({ type: 'set', payload: { loading: true, error: null } });
    try {
      const response = await fetch('/api/twilio/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity: state.identity || undefined }),
      });
      if (!response.ok) {
        throw new Error(`获取 Token 失败：${response.status}`);
      }
      const data: { identity: string; token: string } = await response.json();
      if (!state.identity) {
        dispatch({ type: 'set', payload: { identity: data.identity } });
      }

      if (deviceRef.current) {
        await deviceRef.current.unregister().catch(() => {});
        deviceRef.current.destroy();
        deviceRef.current = null;
      }

      const device = new Device(data.token, {
        logLevel: 'error',
        codecPreferences: ['opus', 'pcmu'],
      });
      device.on('registered', () => {
        appendLog('Twilio Device registered');
        dispatch({ type: 'set', payload: { status: 'ready' } });
      });
      device.on('unregistered', () => appendLog('Twilio Device unregistered'));
      device.on('error', (deviceError) => {
        appendLog(`Device error: ${deviceError.message}`);
        dispatch({ type: 'set', payload: { error: deviceError.message } });
      });
      deviceRef.current = device;
      await device.register();
      if (!state.dialNumber.trim()) {
        dispatch({ type: 'set', payload: { dialNumber: DEFAULT_TWILIO_NUMBER } });
      }
      appendLog('Device initialized');
    } catch (err) {
      const message = err instanceof Error ? err.message : '初始化失败';
      dispatch({ type: 'set', payload: { error: message, status: 'error' } });
      appendLog(message);
    } finally {
      dispatch({ type: 'set', payload: { loading: false } });
    }
  }, [appendLog, state.dialNumber, state.identity, state.loading]);

  const startCall = useCallback(async () => {
    if (state.status !== 'ready' || !deviceRef.current) {
      dispatch({ type: 'set', payload: { error: '请先初始化 Twilio Device。' } });
      return;
    }
    const trimmed = state.dialNumber.trim();
    if (!trimmed) {
      dispatch({ type: 'set', payload: { error: '请输入要拨打的号码。' } });
      return;
    }
    dispatch({ type: 'set', payload: { error: null, status: 'calling' } });
    appendLog(`Dialing ${trimmed} ...`);
    try {
      const params: Record<string, string> = { To: trimmed };
      if (promptId) {
        params.PromptId = promptId;
      }
      const call = await deviceRef.current.connect({ params });
      activeCallRef.current = call;
      call.on('accept', () => appendLog('Call accepted'));
      call.on('disconnect', () => {
        appendLog('Call disconnected');
        dispatch({ type: 'set', payload: { status: 'ready' } });
        activeCallRef.current = null;
      });
      call.on('cancel', () => {
        appendLog('Call canceled');
        dispatch({ type: 'set', payload: { status: 'ready' } });
        activeCallRef.current = null;
      });
      call.on('error', (callError) => {
        appendLog(`Call error: ${callError.message}`);
        dispatch({ type: 'set', payload: { error: callError.message, status: 'ready' } });
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : '呼叫失败';
      appendLog(message);
      dispatch({ type: 'set', payload: { error: message, status: 'ready' } });
    }
  }, [appendLog, promptId, state.dialNumber, state.status]);

  const hangup = useCallback(() => {
    if (activeCallRef.current) {
      activeCallRef.current.disconnect();
      activeCallRef.current = null;
      appendLog('Call disconnected by user');
      dispatch({ type: 'set', payload: { status: 'ready' } });
    }
  }, [appendLog]);

  useEffect(
    () => () => {
      if (activeCallRef.current) {
        activeCallRef.current.disconnect();
      }
      if (deviceRef.current) {
        deviceRef.current.destroy();
      }
    },
    [],
  );

  return {
    identity: state.identity,
    setIdentity,
    dialNumber: state.dialNumber,
    setDialNumber,
    status: state.status,
    loading: state.loading,
    error: state.error,
    logs: state.logs,
    initializeDevice,
    startCall,
    hangup,
    clearError,
  };
}
