import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { http } from '../../../../../api/http';

export type DialerStatus = 'idle' | 'fetching_token' | 'registering' | 'registered' | 'error';
export type CallStatus = 'idle' | 'dialing' | 'in-call' | 'ended' | 'error';
export type GatewayLogLevel = 'info' | 'success' | 'warning' | 'error';
export type TwilioTransportMode = 'conversationrelay' | 'media_stream_live';

export interface DialerLogItem {
  id: string;
  level: GatewayLogLevel;
  time: string;
  message: string;
}

export interface TwilioTraceEvent {
  seq: number;
  ts: number;
  type: string;
  level?: GatewayLogLevel;
  text?: string;
  final?: boolean;
}

export type TwilioTtsProvider = 'Google' | 'Amazon' | 'ElevenLabs';

export interface TwilioVoiceCatalog {
  provider: TwilioTtsProvider;
  providers: TwilioTtsProvider[];
  voices: string[];
  source: string;
  defaultVoice: string;
  language: string;
}

export interface TwilioCapabilitySnapshot {
  configuredPhoneNumber: string;
  geminiGenerateImplemented: boolean;
  geminiLiveImplemented: boolean;
  twilioWebcallImplemented: boolean;
}

interface StartDialOptions {
  promptCode: string;
  transportMode: TwilioTransportMode;
  ttsProvider?: TwilioTtsProvider;
  voiceName?: string;
}

interface PrepareInboundCallOptions {
  promptCode: string;
  transportMode: TwilioTransportMode;
  ttsProvider?: TwilioTtsProvider;
  voiceName?: string;
}

interface UseTwilioVoiceGatewayOptions {
  identity: string;
}

export interface UseTwilioVoiceGatewayResult {
  capability: TwilioCapabilitySnapshot;
  voiceCatalog: TwilioVoiceCatalog;
  loadingCapability: boolean;
  loadingVoices: boolean;
  targetNumber: string;
  setTargetNumber: (value: string) => void;
  targetNumberLocked: boolean;
  dialerStatus: DialerStatus;
  callStatus: CallStatus;
  token: string;
  traceCallSid: string;
  traceSeq: number;
  traceEvents: TwilioTraceEvent[];
  logs: DialerLogItem[];
  info: string | null;
  error: string | null;
  setInfo: (value: string | null) => void;
  setError: (value: string | null) => void;
  refreshCapability: () => Promise<void>;
  refreshVoiceCatalog: (options?: {
    forceRefresh?: boolean;
    provider?: TwilioTtsProvider;
  }) => Promise<void>;
  fetchToken: () => Promise<string>;
  registerDevice: () => Promise<void>;
  startDial: (options: StartDialOptions) => Promise<void>;
  prepareInboundCall: (options: PrepareInboundCallOptions) => Promise<void>;
  hangupCall: () => void;
  unregisterDevice: () => void;
  resetGatewaySession: (options?: { clearMessages?: boolean }) => void;
}

const TRACE_POLL_INTERVAL_MS = 1200;
const TRACE_MAX_EVENTS = 300;

function formatLogTime(date = new Date()): string {
  return date.toLocaleTimeString('zh-CN', { hour12: false });
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

export function useTwilioVoiceGateway({
  identity,
}: UseTwilioVoiceGatewayOptions): UseTwilioVoiceGatewayResult {
  const [capability, setCapability] = useState<TwilioCapabilitySnapshot>({
    configuredPhoneNumber: '',
    geminiGenerateImplemented: false,
    geminiLiveImplemented: false,
    twilioWebcallImplemented: false,
  });
  const [voiceCatalog, setVoiceCatalog] = useState<TwilioVoiceCatalog>({
    provider: 'Google',
    providers: ['Google', 'Amazon', 'ElevenLabs'],
    voices: [],
    source: 'unknown',
    defaultVoice: '',
    language: 'ja-JP',
  });
  const [loadingCapability, setLoadingCapability] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);

  const [targetNumber, setTargetNumberState] = useState('');
  const [targetNumberLocked, setTargetNumberLocked] = useState(false);
  const [dialerStatus, setDialerStatus] = useState<DialerStatus>('idle');
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [token, setToken] = useState('');
  const [logs, setLogs] = useState<DialerLogItem[]>([]);
  const [traceCallSid, setTraceCallSid] = useState('');
  const [traceSeq, setTraceSeq] = useState(0);
  const [traceEvents, setTraceEvents] = useState<TwilioTraceEvent[]>([]);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deviceRef = useRef<any>(null);
  const callRef = useRef<any>(null);
  const tracePollingTimerRef = useRef<number | null>(null);
  const traceCallSidRef = useRef('');
  const traceSeqRef = useRef(0);
  const dialerStatusRef = useRef<DialerStatus>('idle');
  const capabilityRequestRef = useRef<AbortController | null>(null);
  const voiceCatalogRequestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    traceCallSidRef.current = traceCallSid;
  }, [traceCallSid]);

  useEffect(() => {
    traceSeqRef.current = traceSeq;
  }, [traceSeq]);

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

  const stopTracePolling = useCallback(() => {
    if (tracePollingTimerRef.current !== null) {
      window.clearInterval(tracePollingTimerRef.current);
      tracePollingTimerRef.current = null;
    }
  }, []);

  const resetGatewaySession = useCallback(
    (options?: { clearMessages?: boolean }) => {
      stopTracePolling();
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
      setTraceCallSid('');
      setTraceSeq(0);
      setTraceEvents([]);
      traceCallSidRef.current = '';
      traceSeqRef.current = 0;
      if (options?.clearMessages) {
        setError(null);
        setInfo(null);
      }
    },
    [stopTracePolling]
  );

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
      const configuredNumber = String(twilioWebcall.configured_phone_number ?? '').trim();

      setCapability({
        configuredPhoneNumber: configuredNumber,
        twilioWebcallImplemented: String(twilioWebcall.status ?? '') === 'implemented',
        geminiGenerateImplemented: String(geminiGenerateGateway.status ?? '') === 'implemented',
        geminiLiveImplemented: String(geminiLiveGateway.status ?? '') === 'implemented',
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

  const refreshVoiceCatalog = useCallback(async (options?: {
    forceRefresh?: boolean;
    provider?: TwilioTtsProvider;
  }) => {
    voiceCatalogRequestRef.current?.abort();
    const controller = new AbortController();
    voiceCatalogRequestRef.current = controller;
    setLoadingVoices(true);
    try {
      const response = await http.get('/twilio/voice/conversationrelay/voices', {
        params: {
          force_refresh: Boolean(options?.forceRefresh),
          tts_provider: options?.provider,
        },
        signal: controller.signal,
      });
      const payload = asRecord(asRecord(response.data).data);
      const voices = Array.isArray(payload.voices)
        ? payload.voices.filter((voice): voice is string => typeof voice === 'string' && voice.trim().length > 0)
        : [];
      const fallbackProviders: TwilioTtsProvider[] = ['Google', 'Amazon', 'ElevenLabs'];
      const providers = Array.isArray(payload.providers)
        ? payload.providers.filter(
            (provider): provider is TwilioTtsProvider =>
              provider === 'Google' || provider === 'Amazon' || provider === 'ElevenLabs'
          )
        : fallbackProviders;
      const providerValue =
        fallbackProviders.includes(String(payload.provider) as TwilioTtsProvider)
        ? (String(payload.provider) as TwilioTtsProvider)
        : providers[0] || 'Google';

      setVoiceCatalog({
        provider: providerValue,
        providers,
        voices,
        source: String(payload.source ?? 'unknown'),
        defaultVoice: String(payload.default_voice ?? '').trim(),
        language: String(payload.language ?? 'ja-JP').trim() || 'ja-JP',
      });
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
      setError(`加载电话网关音色失败: ${message}`);
    } finally {
      if (!controller.signal.aborted) {
        setLoadingVoices(false);
      }
      if (voiceCatalogRequestRef.current === controller) {
        voiceCatalogRequestRef.current = null;
      }
    }
  }, []);

  const pollTraceOnce = useCallback(async () => {
    let activeCallSid = traceCallSidRef.current.trim();
    try {
      const resolveLatestActiveCallSid = async (): Promise<string> => {
        const activeResponse = await http.get('/twilio/voice/trace/active');
        const activePayload = asRecord(asRecord(activeResponse.data).data);
        const activeCalls = Array.isArray(activePayload.active_calls)
          ? activePayload.active_calls.filter(
              (item): item is string => typeof item === 'string' && item.trim().length > 0
            )
          : [];
        if (activeCalls.length > 0) {
          return activeCalls[activeCalls.length - 1].trim();
        }
        const latestResponse = await http.get('/twilio/voice/trace/latest');
        const latestPayload = asRecord(asRecord(latestResponse.data).data);
        return String(latestPayload.call_sid ?? '').trim();
      };

      if (!activeCallSid) {
        activeCallSid = await resolveLatestActiveCallSid();

        if (!activeCallSid) return;
        traceCallSidRef.current = activeCallSid;
        traceSeqRef.current = 0;
        setTraceCallSid(activeCallSid);
        setTraceSeq(0);
        setTraceEvents([]);
      }

      const response = await http.get('/twilio/voice/trace', {
        params: {
          call_sid: activeCallSid,
          since: traceSeqRef.current,
        },
      });
      const payload = asRecord(asRecord(response.data).data);
      const eventsRaw = Array.isArray(payload.events) ? payload.events : [];
      const incomingEvents: TwilioTraceEvent[] = eventsRaw
        .map((item) => asRecord(item))
        .map((item) => ({
          seq: Number(item.seq ?? 0),
          ts: Number(item.ts ?? Date.now()),
          type: String(item.type ?? ''),
          level: ['info', 'success', 'warning', 'error'].includes(String(item.level))
            ? (String(item.level) as GatewayLogLevel)
            : undefined,
          text: typeof item.text === 'string' ? item.text : undefined,
          final: typeof item.final === 'boolean' ? item.final : undefined,
        }))
        .filter((item) => item.seq > 0);

      const lastSeq = Number(payload.last_seq ?? traceSeqRef.current);
      if (incomingEvents.length === 0 && traceSeqRef.current === 0) {
        const fallbackCallSid = await resolveLatestActiveCallSid();
        if (fallbackCallSid && fallbackCallSid !== activeCallSid) {
          traceCallSidRef.current = fallbackCallSid;
          traceSeqRef.current = 0;
          setTraceCallSid(fallbackCallSid);
          setTraceSeq(0);
          setTraceEvents([]);
          return;
        }
      }
      if (incomingEvents.length > 0) {
        setTraceEvents((prev) => [...prev, ...incomingEvents].slice(-TRACE_MAX_EVENTS));
      }
      if (Number.isFinite(lastSeq) && lastSeq >= traceSeqRef.current) {
        traceSeqRef.current = lastSeq;
        setTraceSeq(lastSeq);
      }
    } catch (pollError) {
      const message = pollError instanceof Error ? pollError.message : String(pollError);
      appendLog('warning', `转写轮询失败: ${message}`);
    }
  }, [appendLog]);

  useEffect(() => {
    const shouldPoll = callStatus === 'dialing' || callStatus === 'in-call';
    if (!shouldPoll) {
      stopTracePolling();
      return;
    }
    void pollTraceOnce();
    tracePollingTimerRef.current = window.setInterval(() => {
      void pollTraceOnce();
    }, TRACE_POLL_INTERVAL_MS);
    return () => {
      stopTracePolling();
    };
  }, [callStatus, pollTraceOnce, stopTracePolling]);

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
                }
              : requestedAudio
                ? {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
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
        const message = String(deviceError?.message || 'Unknown device error');
        setDialerStatus('error');
        setError(`Twilio Device 错误: ${message}`);
        appendLog('error', `Twilio Device 错误: ${message}`);
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
      const message = registerError instanceof Error ? registerError.message : String(registerError);
      setDialerStatus('error');
      setError(`注册设备失败: ${message}`);
      appendLog('error', `注册设备失败: ${message}`);
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
        const message = String(callError?.message || 'Unknown call error');
        setCallStatus('error');
        setError(`通话错误: ${message}`);
        appendLog('error', `通话错误: ${message}`);
      });
    },
    [appendLog]
  );

  const startDial = useCallback(
    async ({ promptCode, transportMode, ttsProvider, voiceName }: StartDialOptions) => {
      try {
        setError(null);
        setInfo(null);
        const target = targetNumber.trim();
        if (!target) {
          setError('请先配置有效的目标号码（E.164）。');
          return;
        }
        if (!promptCode.trim()) {
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

        setTraceEvents([]);
        setTraceSeq(0);
        setTraceCallSid('');
        traceSeqRef.current = 0;
        traceCallSidRef.current = '';

        setCallStatus('dialing');
        appendLog('info', `正在拨号 ${target} ...`);

        const params: Record<string, string> = {
          To: target,
          prompt_code: promptCode,
        };
        if (transportMode === 'media_stream_live') {
          params.voice_route = 'media_stream_live';
        } else {
          params.voice_route = 'conversationrelay_generate';
          params.voice_engine = 'gemini';
        }
        const normalizedTtsProvider = (ttsProvider || '').trim();
        if (transportMode === 'conversationrelay' && normalizedTtsProvider) {
          params.tts_provider = normalizedTtsProvider;
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
          setTraceCallSid(callSid);
          traceCallSidRef.current = callSid;
        }

        setInfo(
          transportMode === 'media_stream_live'
            ? '已发起通话，当前链路为 Twilio Media Streams -> Gemini Live 音频双向桥接。'
            : '已发起通话，当前链路为 Twilio ConversationRelay -> Gemini 文本流式生成。'
        );
      } catch (dialError) {
        const message = dialError instanceof Error ? dialError.message : String(dialError);
        setCallStatus('error');
        setError(`拨号失败: ${message}`);
        appendLog('error', `拨号失败: ${message}`);
      }
    },
    [appendLog, bindCallEvents, registerDevice, targetNumber]
  );

  const prepareInboundCall = useCallback(
    async ({ promptCode, transportMode, ttsProvider, voiceName }: PrepareInboundCallOptions) => {
      try {
        setError(null);
        setInfo(null);
        const inboundNumber = (capability.configuredPhoneNumber || targetNumber).trim();
        if (!inboundNumber) {
          setError('当前没有可用的 Twilio 入站号码。请先检查后端 TWILIO_PHONE_NUMBER 配置。');
          return;
        }
        if (!promptCode.trim()) {
          setError('请先选择 Prompt 模板。');
          return;
        }

        const response = await http.post('/twilio/voice/incoming/prepare', {
          to_number: inboundNumber,
          prompt_code: promptCode,
          voice_route:
            transportMode === 'media_stream_live'
              ? 'media_stream_live'
              : 'conversationrelay_generate',
          voice_engine: transportMode === 'conversationrelay' ? 'gemini' : undefined,
          tts_provider:
            transportMode === 'conversationrelay'
              ? (ttsProvider || '').trim() || undefined
              : undefined,
          voice_name: (voiceName || '').trim() || undefined,
        });
        const data = asRecord(asRecord(response.data).data);
        const expiresIn = Number(data.expires_in_seconds ?? 0);
        const resolvedNumber = String(data.to_number ?? inboundNumber).trim() || inboundNumber;
        const resolvedPrompt = String(data.prompt_code ?? promptCode).trim() || promptCode;
        const resolvedRoute = String(data.voice_route ?? '').trim();
        const resolvedProvider = String(data.tts_provider ?? '').trim();
        const resolvedVoice = String(data.voice_name ?? '').trim();

        appendLog(
          'success',
          `已准备下一通入呼：${resolvedNumber}，Prompt=${resolvedPrompt}${
            resolvedRoute ? `，Route=${resolvedRoute}` : ''
          }${resolvedProvider ? `，Provider=${resolvedProvider}` : ''}${resolvedVoice ? `，Voice=${resolvedVoice}` : ''}。`
        );
        setInfo(
          transportMode === 'media_stream_live'
            ? `已为 ${resolvedNumber} 准备下一通入呼，${expiresIn || 180} 秒内拨入该 Twilio 号码会使用 Prompt ${resolvedPrompt}，并走 Twilio Media Streams -> Gemini Live${resolvedVoice ? `，音色 ${resolvedVoice}` : ''}。`
            : `已为 ${resolvedNumber} 准备下一通入呼，${expiresIn || 180} 秒内拨入该 Twilio 号码会使用 Prompt ${resolvedPrompt}${
                resolvedProvider ? `、${resolvedProvider} 语音层` : ''
              }${
                resolvedVoice ? ` 与音色 ${resolvedVoice}` : ''
              }。`
        );
      } catch (prepareError) {
        const message = prepareError instanceof Error ? prepareError.message : String(prepareError);
        setError(`准备入呼失败: ${message}`);
        appendLog('error', `准备入呼失败: ${message}`);
      }
    },
    [appendLog, capability.configuredPhoneNumber, targetNumber]
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
      voiceCatalogRequestRef.current?.abort();
      voiceCatalogRequestRef.current = null;
      resetGatewaySession();
    };
  }, [resetGatewaySession]);

  return useMemo(
    () => ({
      capability,
      voiceCatalog,
      loadingCapability,
      loadingVoices,
      targetNumber,
      setTargetNumber,
      targetNumberLocked,
      dialerStatus,
      callStatus,
      token,
      traceCallSid,
      traceSeq,
      traceEvents,
      logs,
      info,
      error,
      setInfo,
      setError,
      refreshCapability,
      refreshVoiceCatalog,
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
      loadingVoices,
      logs,
      prepareInboundCall,
      refreshCapability,
      refreshVoiceCatalog,
      registerDevice,
      resetGatewaySession,
      setTargetNumber,
      startDial,
      targetNumber,
      targetNumberLocked,
      token,
      traceCallSid,
      traceEvents,
      traceSeq,
      unregisterDevice,
      voiceCatalog,
    ]
  );
}
