import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { API_BASE_URL, buildApiRequestHeaders, http } from '../../../../../api/http';
import type { BackendTraceDiagnosticResponse } from '../../diagnostics';

export type DialerStatus = 'idle' | 'fetching_token' | 'registering' | 'registered' | 'error';
export type CallStatus = 'idle' | 'dialing' | 'in-call' | 'ended' | 'error';
export type GatewayLogLevel = 'info' | 'success' | 'warning' | 'error';
export type TwilioTransportMode = 'media_stream_live';

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

export interface TwilioActiveTraceCall {
  callSid: string;
  lastSeq: number;
  eventCount: number;
  lastEventType: string;
  lastEventTs: number;
  lastEventText?: string;
}

export interface TwilioCapabilitySnapshot {
  configuredPhoneNumber: string;
  geminiGenerateImplemented: boolean;
  geminiLiveImplemented: boolean;
  twilioWebcallImplemented: boolean;
}

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
  promptCode: string;
  voiceName?: string;
}

interface PrepareInboundCallOptions {
  promptCode: string;
  voiceName?: string;
}

interface UseTwilioVoiceGatewayOptions {
  identity: string;
}

export interface UseTwilioVoiceGatewayResult {
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
  const [loadingCapability, setLoadingCapability] = useState(false);

  const [targetNumber, setTargetNumberState] = useState('');
  const [targetNumberLocked, setTargetNumberLocked] = useState(false);
  const [dialerStatus, setDialerStatus] = useState<DialerStatus>('idle');
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [token, setToken] = useState('');
  const [logs, setLogs] = useState<DialerLogItem[]>([]);
  const [sdkCallSid, setSdkCallSid] = useState('');
  const [traceCallSid, setTraceCallSid] = useState('');
  const [traceSeq, setTraceSeq] = useState(0);
  const [traceEvents, setTraceEvents] = useState<TwilioTraceEvent[]>([]);
  const [activeTraceCalls, setActiveTraceCalls] = useState<TwilioActiveTraceCall[]>([]);
  const [inboundDebugAudioPcm8kUrl, setInboundDebugAudioPcm8kUrl] = useState('');
  const [inboundDebugAudioPcm16kUrl, setInboundDebugAudioPcm16kUrl] = useState('');
  const [inboundDebugAudioSummaryText, setInboundDebugAudioSummaryText] = useState('');
  const [loadingInboundDebugAudio, setLoadingInboundDebugAudio] = useState(false);
  const [traceDiagnostic, setTraceDiagnostic] = useState<BackendTraceDiagnosticResponse | null>(null);
  const [loadingTraceDiagnostic, setLoadingTraceDiagnostic] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deviceRef = useRef<any>(null);
  const callRef = useRef<any>(null);
  const tracePollingTimerRef = useRef<number | null>(null);
  const traceCallSidRef = useRef('');
  const traceSeqRef = useRef(0);
  const dialerStatusRef = useRef<DialerStatus>('idle');
  const capabilityRequestRef = useRef<AbortController | null>(null);
  const inboundDebugAudioPcm8kUrlRef = useRef('');
  const inboundDebugAudioPcm16kUrlRef = useRef('');
  const inboundDebugAudioSeqRef = useRef(0);
  const inboundDebugAudioRequestRef = useRef<AbortController | null>(null);

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

  const clearInboundDebugAudio = useCallback(() => {
    inboundDebugAudioRequestRef.current?.abort();
    inboundDebugAudioRequestRef.current = null;
    inboundDebugAudioSeqRef.current = 0;
    if (inboundDebugAudioPcm8kUrlRef.current) {
      URL.revokeObjectURL(inboundDebugAudioPcm8kUrlRef.current);
      inboundDebugAudioPcm8kUrlRef.current = '';
    }
    if (inboundDebugAudioPcm16kUrlRef.current) {
      URL.revokeObjectURL(inboundDebugAudioPcm16kUrlRef.current);
      inboundDebugAudioPcm16kUrlRef.current = '';
    }
    setInboundDebugAudioPcm8kUrl('');
    setInboundDebugAudioPcm16kUrl('');
    setInboundDebugAudioSummaryText('');
    setLoadingInboundDebugAudio(false);
  }, []);

  const clearTraceBinding = useCallback(() => {
    clearInboundDebugAudio();
    setTraceCallSid('');
    setTraceSeq(0);
    setTraceEvents([]);
    setActiveTraceCalls([]);
    setTraceDiagnostic(null);
    traceCallSidRef.current = '';
    traceSeqRef.current = 0;
  }, [clearInboundDebugAudio]);

  const bindTraceCallSid = useCallback(
    (nextCallSid: string) => {
      const normalizedCallSid = nextCallSid.trim();
      if (!normalizedCallSid) {
        clearTraceBinding();
        return;
      }
      if (traceCallSidRef.current.trim() === normalizedCallSid) {
        return;
      }
      traceCallSidRef.current = normalizedCallSid;
      traceSeqRef.current = 0;
      setTraceCallSid(normalizedCallSid);
      setTraceSeq(0);
      setTraceEvents([]);
      setTraceDiagnostic(null);
    },
    [clearTraceBinding]
  );

  const loadActiveTraceCalls = useCallback(async (): Promise<{
    latestCallSid: string;
    activeCalls: TwilioActiveTraceCall[];
  }> => {
    const activeResponse = await http.get('/twilio/voice/trace/active');
    const activePayload = asRecord(asRecord(activeResponse.data).data);
    const detailItems = Array.isArray(activePayload.active_call_details)
      ? activePayload.active_call_details.map((item) => asRecord(item))
      : [];
    const parsedDetails: TwilioActiveTraceCall[] = detailItems
      .map((item) => ({
        callSid: String(item.call_sid ?? '').trim(),
        lastSeq: Number(item.last_seq ?? 0),
        eventCount: Number(item.event_count ?? 0),
        lastEventType: String(item.last_event_type ?? '').trim(),
        lastEventTs: Number(item.last_event_ts ?? 0),
        lastEventText: String(item.last_event_text ?? '').trim() || undefined,
      }))
      .filter((item) => item.callSid.length > 0);

    const fallbackCalls =
      parsedDetails.length > 0
        ? parsedDetails
        : (Array.isArray(activePayload.active_calls) ? activePayload.active_calls : [])
            .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
            .map((callSid) => ({
              callSid: callSid.trim(),
              lastSeq: 0,
              eventCount: 0,
              lastEventType: '',
              lastEventTs: 0,
            }));

    setActiveTraceCalls(fallbackCalls);

    const latestCallSid =
      String(activePayload.latest_call_sid ?? '').trim() || fallbackCalls[0]?.callSid || '';
    return {
      latestCallSid,
      activeCalls: fallbackCalls,
    };
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
      setSdkCallSid('');
      clearTraceBinding();
      setLoadingTraceDiagnostic(false);
      if (options?.clearMessages) {
        setError(null);
        setInfo(null);
      }
    },
    [clearTraceBinding, stopTracePolling]
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

  const pollTraceOnce = useCallback(async () => {
    let activeCallSid = traceCallSidRef.current.trim();
    try {
      let activeTraceState:
        | {
            latestCallSid: string;
            activeCalls: TwilioActiveTraceCall[];
          }
        | undefined;
      const resolveActiveTraceState = async () => {
        if (!activeTraceState) {
          activeTraceState = await loadActiveTraceCalls();
        }
        return activeTraceState;
      };

      if (!activeCallSid) {
        const activeState = await resolveActiveTraceState();
        activeCallSid = activeState.latestCallSid;
        if (!activeCallSid) return;
        bindTraceCallSid(activeCallSid);
      } else {
        const activeState = await resolveActiveTraceState();
        const isBoundCallStillActive = activeState.activeCalls.some((item) => item.callSid === activeCallSid);
        if (!isBoundCallStillActive && activeState.latestCallSid && activeState.latestCallSid !== activeCallSid) {
          activeCallSid = activeState.latestCallSid;
          bindTraceCallSid(activeCallSid);
          return;
        }
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
        const activeState = await resolveActiveTraceState();
        if (activeState.latestCallSid && activeState.latestCallSid !== activeCallSid) {
          bindTraceCallSid(activeState.latestCallSid);
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

      setLoadingTraceDiagnostic(true);
      try {
        const diagnosticResponse = await http.get('/twilio/voice/trace/diagnostics', {
          params: {
            call_sid: activeCallSid,
          },
        });
        const diagnosticPayload = asRecord(asRecord(diagnosticResponse.data).data);
        setTraceDiagnostic({
          call_sid: String(diagnosticPayload.call_sid ?? activeCallSid).trim() || activeCallSid,
          status: ['ok', 'warning', 'error', 'unknown'].includes(String(diagnosticPayload.status))
            ? (String(diagnosticPayload.status) as BackendTraceDiagnosticResponse['status'])
            : 'unknown',
          category: String(diagnosticPayload.category ?? 'unknown'),
          owner: String(diagnosticPayload.owner ?? 'unknown'),
          title: String(diagnosticPayload.title ?? '未提供诊断标题'),
          summary: String(diagnosticPayload.summary ?? ''),
          actions: Array.isArray(diagnosticPayload.actions)
            ? diagnosticPayload.actions
                .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                .slice(0, 4)
            : [],
          evidence: Array.isArray(diagnosticPayload.evidence)
            ? diagnosticPayload.evidence
                .map((item) => asRecord(item))
                .map((item) => ({
                  seq: Number(item.seq ?? 0),
                  ts: Number(item.ts ?? 0),
                  type: String(item.type ?? ''),
                  level: ['info', 'success', 'warning', 'error'].includes(String(item.level))
                    ? (String(item.level) as GatewayLogLevel)
                    : 'info',
                  text: String(item.text ?? ''),
                }))
                .filter((item) => item.seq > 0 || item.text.trim().length > 0)
            : [],
          last_seq: Number(diagnosticPayload.last_seq ?? lastSeq),
          stream_active: Boolean(diagnosticPayload.stream_active),
        });
      } finally {
        setLoadingTraceDiagnostic(false);
      }
    } catch (pollError) {
      const message = pollError instanceof Error ? pollError.message : String(pollError);
      appendLog('warning', `转写轮询失败: ${message}`);
      setLoadingTraceDiagnostic(false);
    }
  }, [appendLog, bindTraceCallSid, loadActiveTraceCalls]);

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

  useEffect(() => {
    const shouldRefreshFinalTrace =
      (callStatus === 'ended' || callStatus === 'error') &&
      (traceCallSidRef.current.trim().length > 0 || sdkCallSid.trim().length > 0);
    if (!shouldRefreshFinalTrace) {
      return;
    }
    const timer = window.setTimeout(() => {
      void pollTraceOnce();
    }, TRACE_POLL_INTERVAL_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [callStatus, pollTraceOnce, sdkCallSid]);

  useEffect(() => {
    const activeCallSid = traceCallSid.trim();
    const latestSavedAudioEvent = [...traceEvents]
      .reverse()
      .find((event) => event.type === 'inbound_debug_wav_saved' && event.seq > 0);

    if (!activeCallSid) {
      clearInboundDebugAudio();
      return;
    }

    if (!latestSavedAudioEvent) {
      return;
    }

    setInboundDebugAudioSummaryText(latestSavedAudioEvent.text ?? '');
    if (
      inboundDebugAudioSeqRef.current === latestSavedAudioEvent.seq &&
      (inboundDebugAudioPcm8kUrlRef.current || inboundDebugAudioPcm16kUrlRef.current)
    ) {
      return;
    }

    inboundDebugAudioRequestRef.current?.abort();
    const controller = new AbortController();
    inboundDebugAudioRequestRef.current = controller;
    setLoadingInboundDebugAudio(true);

    const loadVariant = async (variant: 'pcm8k_raw' | 'pcm16k_resampled') => {
      const audioUrl =
        `${API_BASE_URL}/twilio/voice/trace/inbound-audio?call_sid=${encodeURIComponent(activeCallSid)}` +
        `&variant=${encodeURIComponent(variant)}`;
      const response = await fetch(audioUrl, {
        method: 'GET',
        headers: buildApiRequestHeaders(),
        signal: controller.signal,
      });
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        (error as Error & { status?: number }).status = response.status;
        throw error;
      }
      const blob = await response.blob();
      return {
        variant,
        blob,
      };
    };

    void Promise.allSettled([loadVariant('pcm8k_raw'), loadVariant('pcm16k_resampled')])
      .then((results) => {
        if (controller.signal.aborted) {
          return;
        }

        let loadedCount = 0;
        let shouldWarn = false;

        for (const result of results) {
          if (result.status !== 'fulfilled') {
            const failure = result.reason as Error & { status?: number };
            if (failure?.status !== 404) {
              shouldWarn = true;
            }
            continue;
          }

          loadedCount += 1;
          const nextUrl = URL.createObjectURL(result.value.blob);
          if (result.value.variant === 'pcm8k_raw') {
            if (inboundDebugAudioPcm8kUrlRef.current) {
              URL.revokeObjectURL(inboundDebugAudioPcm8kUrlRef.current);
            }
            inboundDebugAudioPcm8kUrlRef.current = nextUrl;
            setInboundDebugAudioPcm8kUrl(nextUrl);
            continue;
          }

          if (inboundDebugAudioPcm16kUrlRef.current) {
            URL.revokeObjectURL(inboundDebugAudioPcm16kUrlRef.current);
          }
          inboundDebugAudioPcm16kUrlRef.current = nextUrl;
          setInboundDebugAudioPcm16kUrl(nextUrl);
        }

        if (loadedCount > 0) {
          inboundDebugAudioSeqRef.current = latestSavedAudioEvent.seq;
        } else {
          inboundDebugAudioSeqRef.current = 0;
          if (inboundDebugAudioPcm8kUrlRef.current) {
            URL.revokeObjectURL(inboundDebugAudioPcm8kUrlRef.current);
            inboundDebugAudioPcm8kUrlRef.current = '';
          }
          if (inboundDebugAudioPcm16kUrlRef.current) {
            URL.revokeObjectURL(inboundDebugAudioPcm16kUrlRef.current);
            inboundDebugAudioPcm16kUrlRef.current = '';
          }
          setInboundDebugAudioPcm8kUrl('');
          setInboundDebugAudioPcm16kUrl('');
        }

        if (shouldWarn && loadedCount === 0) {
          appendLog('warning', '入站调试音频加载失败，两个调试样本都未能成功获取。');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingInboundDebugAudio(false);
        }
        if (inboundDebugAudioRequestRef.current === controller) {
          inboundDebugAudioRequestRef.current = null;
        }
      });

    return () => {
      controller.abort();
    };
  }, [appendLog, clearInboundDebugAudio, traceCallSid, traceEvents]);

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

        setSdkCallSid('');
        clearTraceBinding();

        setCallStatus('dialing');
        appendLog('info', `正在拨号 ${target} ...`);

        const params: Record<string, string> = {
          To: target,
          prompt_code: promptCode,
          voice_route: 'media_stream_live',
        };
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

        setInfo('已发起通话，当前链路为 Twilio Media Streams -> Gemini Live 音频双向桥接。');
      } catch (dialError) {
        const message = formatTwilioSdkError('拨号失败', dialError);
        setCallStatus('error');
        setError(message);
        appendLog('error', message);
      }
    },
    [appendLog, bindCallEvents, clearTraceBinding, registerDevice, targetNumber]
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
        if (!promptCode.trim()) {
          setError('请先选择 Prompt 模板。');
          return;
        }

        const response = await http.post('/twilio/voice/incoming/prepare', {
          to_number: inboundNumber,
          prompt_code: promptCode,
          voice_route: 'media_stream_live',
          voice_name: (voiceName || '').trim() || undefined,
        });
        const data = asRecord(asRecord(response.data).data);
        const expiresIn = Number(data.expires_in_seconds ?? 0);
        const resolvedNumber = String(data.to_number ?? inboundNumber).trim() || inboundNumber;
        const resolvedPrompt = String(data.prompt_code ?? promptCode).trim() || promptCode;
        const resolvedRoute = String(data.voice_route ?? '').trim();
        const resolvedVoice = String(data.voice_name ?? '').trim();

        appendLog(
          'success',
          `已准备下一通入呼：${resolvedNumber}，Prompt=${resolvedPrompt}${
            resolvedRoute ? `，Route=${resolvedRoute}` : ''
          }${resolvedVoice ? `，Voice=${resolvedVoice}` : ''}。`
        );
        setInfo(
          `已为 ${resolvedNumber} 准备下一通入呼，${expiresIn || 180} 秒内拨入该 Twilio 号码会使用 Prompt ${resolvedPrompt}，并走 Twilio Media Streams -> Gemini Live${resolvedVoice ? `，音色 ${resolvedVoice}` : ''}。`
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
      clearInboundDebugAudio();
      resetGatewaySession();
    };
  }, [clearInboundDebugAudio, resetGatewaySession]);

  return useMemo(
    () => ({
      capability,
      loadingCapability,
      targetNumber,
      setTargetNumber,
      targetNumberLocked,
      dialerStatus,
      callStatus,
      token,
      sdkCallSid,
      traceCallSid,
      traceSeq,
      traceEvents,
      activeTraceCalls,
      inboundDebugAudioPcm8kUrl,
      inboundDebugAudioPcm16kUrl,
      inboundDebugAudioSummaryText,
      loadingInboundDebugAudio,
      traceDiagnostic,
      loadingTraceDiagnostic,
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
      setTargetNumber,
      startDial,
      sdkCallSid,
      targetNumber,
      targetNumberLocked,
      token,
      activeTraceCalls,
      inboundDebugAudioPcm16kUrl,
      inboundDebugAudioPcm8kUrl,
      inboundDebugAudioSummaryText,
      loadingInboundDebugAudio,
      traceCallSid,
      traceDiagnostic,
      traceEvents,
      traceSeq,
      loadingTraceDiagnostic,
      unregisterDevice,
    ]
  );
}
