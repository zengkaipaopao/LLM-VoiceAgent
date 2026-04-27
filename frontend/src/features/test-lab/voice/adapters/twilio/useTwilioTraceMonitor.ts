import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { API_BASE_URL, buildApiRequestHeaders, http } from '../../../../../api/http';
import type { BackendTraceDiagnosticResponse } from '../../diagnostics';
import type {
  CallStatus,
  GatewayLogLevel,
  TwilioActiveTraceCall,
  TwilioInboundDebugAudioKind,
  TwilioTraceEvent,
} from './twilioGatewayTypes';

interface UseTwilioTraceMonitorOptions {
  callStatus: CallStatus;
  sdkCallSid: string;
  appendLog: (level: GatewayLogLevel, message: string) => void;
}

interface UseTwilioTraceMonitorResult {
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
  bindTraceCallSid: (callSid: string) => void;
  resetTraceMonitor: () => void;
}

const TRACE_POLL_INTERVAL_MS = 1200;
const TRACE_MAX_EVENTS = 300;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

export function useTwilioTraceMonitor({
  callStatus,
  sdkCallSid,
  appendLog,
}: UseTwilioTraceMonitorOptions): UseTwilioTraceMonitorResult {
  const { t } = useTranslation(['pages']);
  const [traceCallSid, setTraceCallSid] = useState('');
  const [traceSeq, setTraceSeq] = useState(0);
  const [traceEvents, setTraceEvents] = useState<TwilioTraceEvent[]>([]);
  const [activeTraceCalls, setActiveTraceCalls] = useState<TwilioActiveTraceCall[]>([]);
  const [inboundDebugAudioPcm8kUrl, setInboundDebugAudioPcm8kUrl] = useState('');
  const [inboundDebugAudioPcm16kUrl, setInboundDebugAudioPcm16kUrl] = useState('');
  const [inboundDebugAudioSummaryText, setInboundDebugAudioSummaryText] = useState('');
  const [inboundDebugAudioKind, setInboundDebugAudioKind] =
    useState<TwilioInboundDebugAudioKind>('none');
  const [loadingInboundDebugAudio, setLoadingInboundDebugAudio] = useState(false);
  const [traceDiagnostic, setTraceDiagnostic] = useState<BackendTraceDiagnosticResponse | null>(null);
  const [loadingTraceDiagnostic, setLoadingTraceDiagnostic] = useState(false);

  const tracePollingTimerRef = useRef<number | null>(null);
  const traceCallSidRef = useRef('');
  const traceSeqRef = useRef(0);
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
    setInboundDebugAudioKind('none');
    setLoadingInboundDebugAudio(false);
  }, []);

  const resetTraceMonitor = useCallback(() => {
    stopTracePolling();
    clearInboundDebugAudio();
    setTraceCallSid('');
    setTraceSeq(0);
    setTraceEvents([]);
    setActiveTraceCalls([]);
    setTraceDiagnostic(null);
    traceCallSidRef.current = '';
    traceSeqRef.current = 0;
  }, [clearInboundDebugAudio, stopTracePolling]);

  const bindTraceCallSid = useCallback(
    (nextCallSid: string) => {
      const normalizedCallSid = nextCallSid.trim();
      if (!normalizedCallSid) {
        resetTraceMonitor();
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
    [resetTraceMonitor]
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

  const loadLatestTraceCallSid = useCallback(async (): Promise<string> => {
    const latestResponse = await http.get('/twilio/voice/trace/latest');
    const latestPayload = asRecord(asRecord(latestResponse.data).data);
    return String(latestPayload.call_sid ?? '').trim();
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
      let latestTraceCallSid: string | undefined;
      const resolveActiveTraceState = async () => {
        if (!activeTraceState) {
          activeTraceState = await loadActiveTraceCalls();
        }
        return activeTraceState;
      };
      const resolveLatestTraceCallSid = async () => {
        if (latestTraceCallSid === undefined) {
          latestTraceCallSid = await loadLatestTraceCallSid();
        }
        return latestTraceCallSid;
      };

      if (!activeCallSid) {
        const activeState = await resolveActiveTraceState();
        activeCallSid = activeState.latestCallSid || (await resolveLatestTraceCallSid());
        if (!activeCallSid) return;
        bindTraceCallSid(activeCallSid);
      } else {
        const activeState = await resolveActiveTraceState();
        const isBoundCallStillActive = activeState.activeCalls.some((item) => item.callSid === activeCallSid);
        const fallbackLatestCallSid = activeState.latestCallSid || (await resolveLatestTraceCallSid());
        if (!isBoundCallStillActive && fallbackLatestCallSid && fallbackLatestCallSid !== activeCallSid) {
          activeCallSid = fallbackLatestCallSid;
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
        const fallbackLatestCallSid = activeState.latestCallSid || (await resolveLatestTraceCallSid());
        if (fallbackLatestCallSid && fallbackLatestCallSid !== activeCallSid) {
          bindTraceCallSid(fallbackLatestCallSid);
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
          title: String(
            diagnosticPayload.title ??
              t('pages:test.voiceLab.diagnostics.fallbackTitle', 'No diagnostic title provided')
          ),
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
      appendLog(
        'warning',
        t('pages:test.voiceLab.gateway.logs.tracePollingFailed', 'Trace polling failed: {{message}}', { message })
      );
      setLoadingTraceDiagnostic(false);
    }
  }, [appendLog, bindTraceCallSid, loadActiveTraceCalls, loadLatestTraceCallSid, t]);

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
    const reversedEvents = [...traceEvents].reverse();
    const latestSavedAudioEvent =
      reversedEvents.find((event) => event.type === 'followup_debug_wav_saved' && event.seq > 0) ??
      reversedEvents.find((event) => event.type === 'inbound_debug_wav_saved' && event.seq > 0);

    if (!activeCallSid) {
      clearInboundDebugAudio();
      return;
    }

    if (!latestSavedAudioEvent) {
      clearInboundDebugAudio();
      return;
    }

    setInboundDebugAudioSummaryText(latestSavedAudioEvent.text ?? '');
    const debugAudioKind: TwilioInboundDebugAudioKind =
      latestSavedAudioEvent.type === 'followup_debug_wav_saved' ? 'followup' : 'tail';
    setInboundDebugAudioKind(debugAudioKind);
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

    const variants =
      debugAudioKind === 'followup'
        ? (['followup_pcm8k_raw', 'followup_pcm16k_resampled'] as const)
        : (['pcm8k_raw', 'pcm16k_resampled'] as const);

    const loadVariant = async (
      variant:
        | 'pcm8k_raw'
        | 'pcm16k_resampled'
        | 'followup_pcm8k_raw'
        | 'followup_pcm16k_resampled'
    ) => {
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

    void Promise.allSettled([loadVariant(variants[0]), loadVariant(variants[1])])
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
          if (result.value.variant === 'pcm8k_raw' || result.value.variant === 'followup_pcm8k_raw') {
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
          setInboundDebugAudioKind('none');
        }

        if (shouldWarn && loadedCount === 0) {
          appendLog(
            'warning',
            t(
              'pages:test.voiceLab.gateway.logs.debugAudioLoadFailed',
              'Failed to load inbound debug audio. Neither debug sample could be retrieved successfully.'
            )
          );
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
  }, [appendLog, clearInboundDebugAudio, t, traceCallSid, traceEvents]);

  useEffect(() => {
    return () => {
      clearInboundDebugAudio();
      stopTracePolling();
    };
  }, [clearInboundDebugAudio, stopTracePolling]);

  return {
    traceCallSid,
    traceSeq,
    traceEvents,
    activeTraceCalls,
    inboundDebugAudioPcm8kUrl,
    inboundDebugAudioPcm16kUrl,
    inboundDebugAudioSummaryText,
    inboundDebugAudioKind,
    loadingInboundDebugAudio,
    traceDiagnostic,
    loadingTraceDiagnostic,
    bindTraceCallSid,
    resetTraceMonitor,
  };
}
