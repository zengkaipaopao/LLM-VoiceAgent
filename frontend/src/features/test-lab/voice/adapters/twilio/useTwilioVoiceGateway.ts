import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { http } from '../../../../../api/http';
import type { BackendTraceDiagnosticResponse } from '../../diagnostics';
import { useTwilioTraceMonitor } from './useTwilioTraceMonitor';
import type {
  CallStatus,
  DialerLogItem,
  DialerStatus,
  GatewayLogLevel,
  TwilioActiveTraceCall,
  TwilioCapabilitySnapshot,
  TwilioInboundDebugAudioKind,
  TwilioTraceEvent,
  TwilioTransportMode,
} from './twilioGatewayTypes';

export type {
  CallStatus,
  DialerLogItem,
  DialerStatus,
  GatewayLogLevel,
  TwilioActiveTraceCall,
  TwilioCapabilitySnapshot,
  TwilioInboundDebugAudioKind,
  TwilioTraceEvent,
  TwilioTransportMode,
} from './twilioGatewayTypes';

function formatTwilioSdkError(prefix: string, rawError: unknown): string {
  const candidate = rawError && typeof rawError === 'object' ? (rawError as Record<string, unknown>) : {};
  const code = String(candidate.code ?? '').trim();
  const name = String(candidate.name ?? '').trim();
  const message = String(candidate.message ?? 'Unknown error').trim();
  const parts = [prefix];
  if (name) {
    parts.push(name);
  }
  if (code) {
    parts.push(`(${code})`);
  }
  return `${parts.join(' ')}: ${message}`;
}

interface StartDialOptions {
  promptCode?: string;
  voiceName?: string;
}

interface PrepareInboundCallOptions {
  promptCode?: string;
  voiceName?: string;
}

interface UseTwilioVoiceGatewayOptions {
  identity: string;
  transportMode?: TwilioTransportMode;
  requirePrompt?: boolean;
  transportLabel?: string;
}

export interface UseTwilioVoiceGatewayResult {
  transportMode: TwilioTransportMode;
  transportLabel: string;
  capability: TwilioCapabilitySnapshot;
  loadingCapability: boolean;
  targetNumber: string;
  setTargetNumber: (value: string) => void;
  targetNumberLocked: boolean;
  dialerStatus: DialerStatus;
  callStatus: CallStatus;
  token: string;
  sdkCallSid: string;
  traceCallSid: string;
  traceSeq: number;
  traceEvents: TwilioTraceEvent[];
  activeTraceCalls: TwilioActiveTraceCall[];
  inboundDebugAudioPcm8kUrl: string;
  inboundDebugAudioPcm16kUrl: string;
  inboundDebugAudioSummaryText: string;
  inboundDebugAudioKind: TwilioInboundDebugAudioKind;
  loadingInboundDebugAudio: boolean;
  traceDiagnostic: BackendTraceDiagnosticResponse | null;
  loadingTraceDiagnostic: boolean;
  logs: DialerLogItem[];
  info: string | null;
  error: string | null;
  setInfo: (value: string | null) => void;
  setError: (value: string | null) => void;
  refreshCapability: () => Promise<void>;
  fetchToken: () => Promise<string>;
  registerDevice: () => Promise<void>;
  startDial: (options: StartDialOptions) => Promise<void>;
  prepareInboundCall: (options: PrepareInboundCallOptions) => Promise<void>;
  hangupCall: () => void;
  unregisterDevice: () => void;
  resetGatewaySession: (options?: { clearMessages?: boolean }) => void;
}

function formatLogTime(date = new Date()): string {
  return date.toLocaleTimeString('zh-CN', { hour12: false });
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

export function useTwilioVoiceGateway({
  identity,
  transportMode = 'official_conversational_agents',
  requirePrompt = true,
  transportLabel = '官方 Conversational Agents（Google CX Agent Studio + Twilio）',
}: UseTwilioVoiceGatewayOptions): UseTwilioVoiceGatewayResult {
  const [capability, setCapability] = useState<TwilioCapabilitySnapshot>({
    configuredPhoneNumber: '',
    geminiGenerateImplemented: false,
    geminiLiveImplemented: false,
    conversationalAgentsImplemented: false,
    twilioWebcallImplemented: false,
  });
  const [loadingCapability, setLoadingCapability] = useState(false);
  const [targetNumber, setTargetNumberState] = useState('');
  const [targetNumberLocked, setTargetNumberLocked] = useState(false);
  const [dialerStatus, setDialerStatus] = useState<DialerStatus>('idle');
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [token, setToken] = useState('');
  const [logs, setLogs] = useState<DialerLogItem[]>([]);
  const [sdkCallSid, setSdkCallSid] = useState('');
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deviceRef = useRef<any>(null);
  const callRef = useRef<any>(null);
  const dialerStatusRef = useRef<DialerStatus>('idle');
  const capabilityRequestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    dialerStatusRef.current = dialerStatus;
  }, [dialerStatus]);

  const appendLog = useCallback((level: GatewayLogLevel, message: string) => {
    setLogs((prev) => [
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        level,
        time: formatLogTime(),
        message,
      },
      ...prev,
    ]);
  }, []);

  const traceMonitor = useTwilioTraceMonitor({
    callStatus,
    sdkCallSid,
    appendLog,
  });
  const resetTraceMonitor = traceMonitor.resetTraceMonitor;

  const refreshCapability = useCallback(async () => {
    capabilityRequestRef.current?.abort();
    const controller = new AbortController();
    capabilityRequestRef.current = controller;
    setLoadingCapability(true);
    try {
      const response = await http.get('/health/capabilities', { signal: controller.signal });
      const matrix = asRecord(asRecord(response.data).data);
      const twilioWebcall = asRecord(matrix.twilio_webcall);
      const geminiGenerateGateway = asRecord(matrix.gemini_generate_gateway);
      const geminiLiveGateway = asRecord(matrix.gemini_live_gateway);
      const conversationalAgentsGateway = asRecord(matrix.google_conversational_agents_twilio_adapter);
      const configuredNumber = String(twilioWebcall.configured_phone_number ?? '').trim();

      setCapability({
        configuredPhoneNumber: configuredNumber,
        twilioWebcallImplemented: String(twilioWebcall.status ?? '') === 'implemented',
        geminiGenerateImplemented: String(geminiGenerateGateway.status ?? '') === 'implemented',
        geminiLiveImplemented: String(geminiLiveGateway.status ?? '') === 'implemented',
        conversationalAgentsImplemented:
          String(conversationalAgentsGateway.status ?? '') === 'implemented',
      });

      if (configuredNumber) {
        setTargetNumberState(configuredNumber);
        setTargetNumberLocked(true);
      } else {
        setTargetNumberLocked(false);
      }
    } catch (loadError) {
      const canceled =
        controller.signal.aborted ||
        (typeof loadError === 'object' &&
          loadError !== null &&
          'name' in loadError &&
          (String((loadError as { name?: unknown }).name) === 'CanceledError' ||
            String((loadError as { name?: unknown }).name) === 'AbortError'));
      if (canceled) {
        return;
      }
      const message = loadError instanceof Error ? loadError.message : String(loadError);
      setError(`加载能力矩阵失败: ${message}`);
    } finally {
      if (!controller.signal.aborted) {
        setLoadingCapability(false);
      }
      if (capabilityRequestRef.current === controller) {
        capabilityRequestRef.current = null;
      }
    }
  }, []);

  const resetGatewaySession = useCallback(
    (options?: { clearMessages?: boolean }) => {
      try {
        if (callRef.current) {
          callRef.current.disconnect();
          callRef.current = null;
        }
        if (deviceRef.current) {
          deviceRef.current.unregister();
          deviceRef.current.destroy?.();
          deviceRef.current = null;
        }
      } catch {
        // noop
      }
      setDialerStatus('idle');
      setCallStatus('idle');
      setSdkCallSid('');
      resetTraceMonitor();
      if (options?.clearMessages) {
        setError(null);
        setInfo(null);
      }
    },
    [resetTraceMonitor]
  );

  const fetchToken = useCallback(async (): Promise<string> => {
    const previousStatus = dialerStatusRef.current;
    setDialerStatus('fetching_token');
    try {
      const response = await http.get('/twilio/token', {
        params: { identity },
      });
      const tokenValue = String(asRecord(asRecord(response.data).data).token ?? '').trim();
      if (!tokenValue) {
        throw new Error('后端未返回可用 Token。');
      }
      setToken(tokenValue);
      appendLog('success', 'Twilio Token 获取成功。');
      setDialerStatus(previousStatus === 'registered' ? 'registered' : 'idle');
      return tokenValue;
    } catch (tokenError) {
      const message = tokenError instanceof Error ? tokenError.message : String(tokenError);
      setDialerStatus('error');
      setError(`获取 Token 失败: ${message}`);
      appendLog('error', `获取 Token 失败: ${message}`);
      throw tokenError;
    }
  }, [appendLog, identity]);

  const registerDevice = useCallback(async () => {
    try {
      setError(null);
      const tokenValue = token || (await fetchToken());
      setDialerStatus('registering');

      if (callRef.current) {
        try {
          callRef.current.disconnect();
        } catch {
          // noop
        }
        callRef.current = null;
      }
      if (deviceRef.current) {
        try {
          deviceRef.current.unregister();
          deviceRef.current.destroy?.();
        } catch {
          // noop
        }
        deviceRef.current = null;
      }

      const { Device } = await import('@twilio/voice-sdk');
      const device = new Device(tokenValue, {
        logLevel: 1,
        codecPreferences: ['opus', 'pcmu'] as unknown as never[],
        getUserMedia: async (constraints?: MediaStreamConstraints) => {
          const requestedAudio =
            constraints && typeof constraints === 'object' && 'audio' in constraints
              ? constraints.audio
              : true;
          const requestedVideo =
            constraints && typeof constraints === 'object' && 'video' in constraints
              ? constraints.video
              : false;

          const audioConstraints =
            requestedAudio && typeof requestedAudio === 'object'
              ? {
                  ...requestedAudio,
                  echoCancellation: true,
                  noiseSuppression: true,
                  autoGainControl: true,
                  channelCount: 1,
                }
              : requestedAudio
                ? {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    channelCount: 1,
                  }
                : requestedAudio;

          return navigator.mediaDevices.getUserMedia({
            audio: audioConstraints,
            video: requestedVideo,
          });
        },
      });
      deviceRef.current = device;

      device.on('registered', () => {
        setDialerStatus('registered');
        appendLog('success', 'Twilio 设备已注册。');
      });
      device.on('unregistered', () => {
        setDialerStatus((previous) => (previous === 'error' ? previous : 'idle'));
        appendLog('info', 'Twilio 设备已注销。');
      });
      device.on('error', (deviceError: any) => {
        const message = formatTwilioSdkError('Twilio Device 错误', deviceError);
        setDialerStatus('error');
        setError(message);
        appendLog('error', message);
      });
      device.on('incoming', (incomingCall: any) => {
        appendLog('warning', '收到入站 client 通话事件，当前测试台仅用于浏览器外呼回归，已自动拒绝。');
        try {
          incomingCall.reject();
        } catch {
          // noop
        }
      });

      await device.register();
    } catch (registerError) {
      const message = formatTwilioSdkError('注册设备失败', registerError);
      setDialerStatus('error');
      setError(message);
      appendLog('error', message);
    }
  }, [appendLog, fetchToken, token]);

  const bindCallEvents = useCallback(
    (call: any) => {
      call.on('ringing', () => {
        setCallStatus('dialing');
        appendLog('info', '对方振铃中...');
      });
      call.on('accept', () => {
        setCallStatus('in-call');
        appendLog('success', '通话已接通。');
      });
      call.on('disconnect', () => {
        setCallStatus('ended');
        appendLog('info', '通话已结束。');
      });
      call.on('cancel', () => {
        setCallStatus('ended');
        appendLog('warning', '通话被取消。');
      });
      call.on('reject', () => {
        setCallStatus('ended');
        appendLog('warning', '通话被拒绝。');
      });
      call.on('error', (callError: any) => {
        const message = formatTwilioSdkError('通话错误', callError);
        setCallStatus('error');
        setError(message);
        appendLog('error', message);
      });
    },
    [appendLog]
  );

  const startDial = useCallback(
    async ({ promptCode, voiceName }: StartDialOptions) => {
      try {
        setError(null);
        setInfo(null);
        const target = targetNumber.trim();
        if (!target) {
          setError('请先配置有效的目标号码（E.164）。');
          return;
        }
        const normalizedPromptCode = (promptCode || '').trim();
        if (requirePrompt && !normalizedPromptCode) {
          setError('请先选择 Prompt 模板。');
          return;
        }

        if (!deviceRef.current || dialerStatusRef.current !== 'registered') {
          await registerDevice();
        }

        const device = deviceRef.current;
        if (!device) {
          setError('Twilio 设备不可用，请先初始化。');
          return;
        }

        setSdkCallSid('');
        resetTraceMonitor();

        setCallStatus('dialing');
        appendLog('info', `正在拨号 ${target} ...`);

        const params: Record<string, string> = {
          To: target,
          voice_route: transportMode,
        };
        if (normalizedPromptCode) {
          params.prompt_code = normalizedPromptCode;
        }
        const normalizedVoiceName = (voiceName || '').trim();
        if (normalizedVoiceName) {
          params.voice_name = normalizedVoiceName;
        }

        const call = await device.connect({ params });
        callRef.current = call;
        bindCallEvents(call);

        const callSid = String(call?.parameters?.CallSid ?? '').trim();
        if (callSid) {
          setSdkCallSid(callSid);
        }

        setInfo(`已发起通话，当前链路为 ${transportLabel}。`);
      } catch (dialError) {
        const message = formatTwilioSdkError('拨号失败', dialError);
        setCallStatus('error');
        setError(message);
        appendLog('error', message);
      }
    },
    [
      appendLog,
      bindCallEvents,
      registerDevice,
      requirePrompt,
      targetNumber,
      resetTraceMonitor,
      transportLabel,
      transportMode,
    ]
  );

  const prepareInboundCall = useCallback(
    async ({ promptCode, voiceName }: PrepareInboundCallOptions) => {
      try {
        setError(null);
        setInfo(null);
        const inboundNumber = (capability.configuredPhoneNumber || targetNumber).trim();
        if (!inboundNumber) {
          setError('当前没有可用的 Twilio 入站号码。请先检查后端 TWILIO_PHONE_NUMBER 配置。');
          return;
        }
        const normalizedPromptCode = (promptCode || '').trim();
        if (requirePrompt && !normalizedPromptCode) {
          setError('请先选择 Prompt 模板。');
          return;
        }

        const response = await http.post('/twilio/voice/incoming/prepare', {
          to_number: inboundNumber,
          prompt_code: normalizedPromptCode || undefined,
          voice_route: transportMode,
          voice_name: (voiceName || '').trim() || undefined,
        });
        const data = asRecord(asRecord(response.data).data);
        const expiresIn = Number(data.expires_in_seconds ?? 0);
        const resolvedNumber = String(data.to_number ?? inboundNumber).trim() || inboundNumber;
        const resolvedPrompt = String(data.prompt_code ?? normalizedPromptCode).trim();
        const resolvedRoute = String(data.voice_route ?? '').trim();
        const resolvedVoice = String(data.voice_name ?? '').trim();

        appendLog(
          'success',
          `已准备下一通入呼：${resolvedNumber}${resolvedPrompt ? `，Prompt=${resolvedPrompt}` : ''}${
            resolvedRoute ? `，Route=${resolvedRoute}` : ''
          }${resolvedVoice ? `，Voice=${resolvedVoice}` : ''}。`
        );
        setInfo(
          `已为 ${resolvedNumber} 准备下一通入呼，${expiresIn || 180} 秒内拨入该 Twilio 号码会使用${
            resolvedPrompt ? ` Prompt ${resolvedPrompt}` : ' Google 官方 Conversational Agents 配置'
          }，并走 ${transportLabel}${resolvedVoice ? `，音色 ${resolvedVoice}` : ''}。`
        );
      } catch (prepareError) {
        const message = prepareError instanceof Error ? prepareError.message : String(prepareError);
        setError(`准备入呼失败: ${message}`);
        appendLog('error', `准备入呼失败: ${message}`);
      }
    },
    [appendLog, capability.configuredPhoneNumber, requirePrompt, targetNumber, transportLabel, transportMode]
  );

  const hangupCall = useCallback(() => {
    try {
      if (callRef.current) {
        callRef.current.disconnect();
        callRef.current = null;
      }
      setCallStatus('ended');
      appendLog('info', '已请求挂断。');
    } catch (hangupError) {
      const message = hangupError instanceof Error ? hangupError.message : String(hangupError);
      setError(`挂断失败: ${message}`);
      appendLog('error', `挂断失败: ${message}`);
    }
  }, [appendLog]);

  const unregisterDevice = useCallback(() => {
    try {
      resetGatewaySession();
      appendLog('info', '设备已注销并重置状态。');
    } catch (unregisterError) {
      const message = unregisterError instanceof Error ? unregisterError.message : String(unregisterError);
      setDialerStatus('error');
      setError(`注销设备失败: ${message}`);
      appendLog('error', `注销设备失败: ${message}`);
    }
  }, [appendLog, resetGatewaySession]);

  const setTargetNumber = useCallback(
    (value: string) => {
      if (targetNumberLocked) {
        return;
      }
      setTargetNumberState(value);
    },
    [targetNumberLocked]
  );

  useEffect(() => {
    return () => {
      capabilityRequestRef.current?.abort();
      capabilityRequestRef.current = null;
      resetGatewaySession();
    };
  }, [resetGatewaySession]);

  return useMemo(
    () => ({
      transportMode,
      transportLabel,
      capability,
      loadingCapability,
      targetNumber,
      setTargetNumber,
      targetNumberLocked,
      dialerStatus,
      callStatus,
      token,
      sdkCallSid,
      traceCallSid: traceMonitor.traceCallSid,
      traceSeq: traceMonitor.traceSeq,
      traceEvents: traceMonitor.traceEvents,
      activeTraceCalls: traceMonitor.activeTraceCalls,
      inboundDebugAudioPcm8kUrl: traceMonitor.inboundDebugAudioPcm8kUrl,
      inboundDebugAudioPcm16kUrl: traceMonitor.inboundDebugAudioPcm16kUrl,
      inboundDebugAudioSummaryText: traceMonitor.inboundDebugAudioSummaryText,
      inboundDebugAudioKind: traceMonitor.inboundDebugAudioKind,
      loadingInboundDebugAudio: traceMonitor.loadingInboundDebugAudio,
      traceDiagnostic: traceMonitor.traceDiagnostic,
      loadingTraceDiagnostic: traceMonitor.loadingTraceDiagnostic,
      logs,
      info,
      error,
      setInfo,
      setError,
      refreshCapability,
      fetchToken,
      registerDevice,
      startDial,
      prepareInboundCall,
      hangupCall,
      unregisterDevice,
      resetGatewaySession,
    }),
    [
      callStatus,
      capability,
      dialerStatus,
      error,
      fetchToken,
      hangupCall,
      info,
      loadingCapability,
      logs,
      prepareInboundCall,
      refreshCapability,
      registerDevice,
      resetGatewaySession,
      sdkCallSid,
      setTargetNumber,
      startDial,
      targetNumber,
      targetNumberLocked,
      token,
      traceMonitor.activeTraceCalls,
      traceMonitor.inboundDebugAudioKind,
      traceMonitor.inboundDebugAudioPcm16kUrl,
      traceMonitor.inboundDebugAudioPcm8kUrl,
      traceMonitor.inboundDebugAudioSummaryText,
      traceMonitor.loadingInboundDebugAudio,
      traceMonitor.loadingTraceDiagnostic,
      traceMonitor.traceCallSid,
      traceMonitor.traceDiagnostic,
      traceMonitor.traceEvents,
      traceMonitor.traceSeq,
      transportLabel,
      transportMode,
      unregisterDevice,
    ]
  );
}
