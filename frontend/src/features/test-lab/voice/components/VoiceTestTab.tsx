import { useEffect, useMemo, useRef, useState } from 'react';
import { Stack, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../../../components/molecules/TestTabs';
import {
  describeVoiceTabOverrideWarning,
  describeVoiceTabPromptModelWarning,
} from '../../../../config/llmModels';
import { VoiceLogsTile } from '../../../../components/organisms/TestTabs/voice/VoiceLogsTile';
import { VoiceRouteSelector } from '../../../../components/organisms/TestTabs/voice/VoiceRouteSelector';
import { VoiceSessionSection } from '../../../../components/organisms/TestTabs/voice/VoiceSessionSection';
import { VoiceSidePanel } from '../../../../components/organisms/TestTabs/voice/VoiceSidePanel';
import type { VoiceRouteMode } from '../../../../components/organisms/TestTabs/voice/types';
import { useTwilioVoiceGateway, type UseTwilioVoiceGatewayResult } from '../adapters/twilio/useTwilioVoiceGateway';
import { useGeminiVoiceCatalog } from '../../../../hooks/useGeminiVoiceCatalog';
import { resolveVoiceRouteTransition } from '../routeMode';
import { matchGeminiLiveVoice, resolveGeminiLiveVoice } from '../voiceSelection';
import { useVoiceTestConsole } from '../hooks/useVoiceTestConsole';
import {
  classifyDirectVoiceDiagnostic,
  classifyGatewayFallbackDiagnostic,
  mapBackendTraceDiagnostic,
} from '../diagnostics';

const DEFAULT_IDENTITY = 'webcall-tester';

function toDialerTone(status: UseTwilioVoiceGatewayResult['dialerStatus']): 'green' | 'blue' | 'cool-gray' | 'red' {
  if (status === 'registered') return 'green';
  if (status === 'fetching_token' || status === 'registering') return 'blue';
  if (status === 'error') return 'red';
  return 'cool-gray';
}

function toCallTone(status: UseTwilioVoiceGatewayResult['callStatus']): 'green' | 'blue' | 'cool-gray' | 'red' {
  if (status === 'in-call') return 'green';
  if (status === 'dialing') return 'blue';
  if (status === 'error') return 'red';
  return 'cool-gray';
}

export function VoiceTestTab() {
  const { t } = useTranslation(['pages']);
  const liveWebsocket = useVoiceTestConsole();
  const twilioGateway = useTwilioVoiceGateway({ identity: DEFAULT_IDENTITY });
  const { voiceCatalog: geminiVoiceCatalog, loadingVoices: loadingGeminiVoices } =
    useGeminiVoiceCatalog();

  const [routeMode, setRouteMode] = useState<VoiceRouteMode>('direct');
  const [twilioMediaStreamVoiceOverride, setTwilioMediaStreamVoiceOverride] = useState('');
  const previousRouteModeRef = useRef<VoiceRouteMode>('direct');
  const twilioConfigBootstrappedRef = useRef(false);

  const prompts = liveWebsocket.prompts;
  const selectedPromptCode = liveWebsocket.selectedPromptCode;
  const resetGatewaySession = twilioGateway.resetGatewaySession;
  const disconnectDirectSession = liveWebsocket.disconnectSocket;
  const clearDirectError = liveWebsocket.setError;
  const selectedPrompt = useMemo(
    () => prompts.find((prompt) => prompt.code === selectedPromptCode),
    [prompts, selectedPromptCode]
  );

  const effectiveVoice = useMemo(() => {
    const supportedGeminiVoices = geminiVoiceCatalog.voices;
    const defaultGeminiVoice = geminiVoiceCatalog.defaultVoice || 'Aoede';

    if (routeMode === 'direct') {
      const directOverrideVoice = (liveWebsocket.voice || '').trim();
      if (directOverrideVoice) return directOverrideVoice;
      const promptVoice = (selectedPrompt?.voiceId || '').trim();
      if (promptVoice) return promptVoice;
      return defaultGeminiVoice;
    }

    const mediaStreamOverride = twilioMediaStreamVoiceOverride.trim();
    if (mediaStreamOverride) {
      return resolveGeminiLiveVoice(mediaStreamOverride, {
        voiceProvider: 'gemini',
        supportedVoices: supportedGeminiVoices,
        defaultVoice: defaultGeminiVoice,
      });
    }

    return resolveGeminiLiveVoice(selectedPrompt?.voiceId, {
      voiceProvider: selectedPrompt?.voiceProvider,
      supportedVoices: supportedGeminiVoices,
      defaultVoice: defaultGeminiVoice,
    });
  }, [
    geminiVoiceCatalog.defaultVoice,
    geminiVoiceCatalog.voices,
    liveWebsocket.voice,
    routeMode,
    selectedPrompt?.voiceId,
    selectedPrompt?.voiceProvider,
    twilioMediaStreamVoiceOverride,
  ]);

  const isPromptVoiceConfigured =
    routeMode === 'twilio'
      ? Boolean(
          matchGeminiLiveVoice(selectedPrompt?.voiceId, {
            voiceProvider: selectedPrompt?.voiceProvider,
            supportedVoices: geminiVoiceCatalog.voices,
          })
        )
      : Boolean((selectedPrompt?.voiceId || '').trim());

  useEffect(() => {
    if (routeMode !== 'twilio') {
      return;
    }
    if (twilioConfigBootstrappedRef.current) {
      return;
    }
    twilioConfigBootstrappedRef.current = true;
    void twilioGateway.refreshCapability();
  }, [routeMode, twilioGateway.refreshCapability]);

  useEffect(() => {
    const previousMode = previousRouteModeRef.current;
    const transition = resolveVoiceRouteTransition(previousMode, routeMode);
    if (transition === 'noop') {
      return;
    }

    if (transition === 'reset_gateway') {
      resetGatewaySession({ clearMessages: true });
    } else {
      disconnectDirectSession();
      clearDirectError(null);
    }

    previousRouteModeRef.current = routeMode;
  }, [clearDirectError, disconnectDirectSession, resetGatewaySession, routeMode]);

  const directMicActive = liveWebsocket.micStatus === 'on' || liveWebsocket.micStatus === 'starting';
  const directSessionActive =
    liveWebsocket.socketStatus === 'connected' ||
    liveWebsocket.socketStatus === 'connecting' ||
    directMicActive;
  const twilioSessionActive = twilioGateway.callStatus === 'dialing' || twilioGateway.callStatus === 'in-call';
  const isAnySessionActive = directSessionActive || twilioSessionActive;
  const configLocked = routeMode === 'direct' ? directSessionActive : twilioSessionActive;

  const canDial =
    twilioGateway.dialerStatus === 'registered' &&
    (twilioGateway.callStatus === 'idle' || twilioGateway.callStatus === 'ended');
  const canHangup = twilioGateway.callStatus === 'dialing' || twilioGateway.callStatus === 'in-call';
  const canDirectConnect =
    liveWebsocket.socketStatus === 'disconnected' || liveWebsocket.socketStatus === 'error';
  const canDirectDisconnect =
    liveWebsocket.socketStatus === 'connected' || liveWebsocket.socketStatus === 'connecting';
  const canDirectToggleMic =
    liveWebsocket.canUseRealtimeInput && liveWebsocket.socketStatus === 'connected';

  const directSocketTone =
    liveWebsocket.socketStatus === 'connected'
      ? 'green'
      : liveWebsocket.socketStatus === 'connecting'
        ? 'blue'
        : liveWebsocket.socketStatus === 'error'
          ? 'red'
          : 'cool-gray';
  const directMicTone =
    liveWebsocket.micStatus === 'on'
      ? 'green'
      : liveWebsocket.micStatus === 'starting'
        ? 'teal'
        : 'cool-gray';

  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'goal',
      label: t('pages:test.voiceLab.summary.goal', 'Test Goal'),
      value: t('pages:test.voiceLab.summary.goalValue', 'Voice connectivity'),
      tone: 'teal',
    },
    {
      id: 'route',
      label: t('pages:test.voiceLab.summary.route', 'Route'),
      value:
        routeMode === 'direct'
          ? t('pages:test.voiceLab.summary.routeDirect', 'Browser direct to Gemini')
          : t('pages:test.voiceLab.summary.routeTwilio', 'Phone gateway (Media Streams)'),
      tone: 'teal',
    },
    {
      id: 'connection',
      label: t('pages:test.voiceLab.summary.connection', 'Connection'),
      value: routeMode === 'direct' ? liveWebsocket.socketStatus : twilioGateway.callStatus,
      tone: routeMode === 'direct' ? directSocketTone : toCallTone(twilioGateway.callStatus),
      mono: true,
    },
    {
      id: 'audio',
      label: t('pages:test.voiceLab.summary.audio', 'Audio Capture'),
      value: routeMode === 'direct' ? liveWebsocket.micStatus : twilioGateway.dialerStatus,
      tone: routeMode === 'direct' ? directMicTone : toDialerTone(twilioGateway.dialerStatus),
      mono: true,
    },
    {
      id: 'prompt',
      label: t('pages:test.voiceLab.summary.prompt', 'Prompt'),
      value: selectedPromptCode || '-',
      mono: true,
    },
    {
      id: 'voice',
      label: t('pages:test.voiceLab.summary.voice', 'Gemini Voice'),
      value: effectiveVoice || '-',
      mono: true,
      tone: routeMode === 'twilio' && isPromptVoiceConfigured ? 'teal' : 'cool-gray',
    },
  ];

  const activeError = routeMode === 'direct' ? liveWebsocket.error : twilioGateway.error;
  const activeInfo = routeMode === 'direct' ? liveWebsocket.info : twilioGateway.info;
  const compatibilityWarning = useMemo(() => {
    const translateModelWarning = (key: string, options: { defaultValue: string; [key: string]: unknown }) =>
      t(key, options);
    const promptWarning = describeVoiceTabPromptModelWarning(
      selectedPrompt?.llmModel,
      selectedPromptCode,
      translateModelWarning
    );
    if (promptWarning) {
      return promptWarning;
    }
    if (routeMode === 'direct') {
      return describeVoiceTabOverrideWarning(liveWebsocket.model, translateModelWarning);
    }
    return null;
  }, [liveWebsocket.model, routeMode, selectedPrompt?.llmModel, selectedPromptCode, t]);
  const directLogs = useMemo(() => [...liveWebsocket.logs].slice(-180).reverse(), [liveWebsocket.logs]);
  const directDiagnostic = useMemo(
    () =>
      classifyDirectVoiceDiagnostic({
        socketStatus: liveWebsocket.socketStatus,
        micStatus: liveWebsocket.micStatus,
        error: liveWebsocket.error,
        logs: liveWebsocket.logs,
        model: liveWebsocket.model,
      }),
    [liveWebsocket.error, liveWebsocket.logs, liveWebsocket.micStatus, liveWebsocket.model, liveWebsocket.socketStatus]
  );
  const twilioDiagnostic = useMemo(
    () =>
      mapBackendTraceDiagnostic(twilioGateway.traceDiagnostic) ||
      classifyGatewayFallbackDiagnostic({
        error: twilioGateway.error,
        dialerStatus: twilioGateway.dialerStatus,
        callStatus: twilioGateway.callStatus,
        logs: twilioGateway.logs,
        traceEvents: twilioGateway.traceEvents,
      }),
    [
      twilioGateway.callStatus,
      twilioGateway.dialerStatus,
      twilioGateway.error,
      twilioGateway.logs,
      twilioGateway.traceDiagnostic,
      twilioGateway.traceEvents,
    ]
  );

  return (
    <TestWorkbenchShell
      title={t('pages:test.voiceLab.shell.title', 'Voice Connectivity Console')}
      description={t(
        'pages:test.voiceLab.shell.description',
        'Validate whether Gemini voice sessions can connect, capture audio, transcribe, and reply.'
      )}
      summaryItems={summaryItems}
      notice={
        <TestTabNotifications
          error={activeError}
          info={activeInfo}
          warning={compatibilityWarning}
          errorTitle={t('pages:test.voiceLab.notifications.errorTitle', 'Request failed')}
          successTitle={t('pages:test.voiceLab.notifications.successTitle', 'Success')}
          warningTitle={t('pages:test.voiceLab.notifications.warningTitle', 'Configuration warning')}
          onClearError={() => {
            if (routeMode === 'direct') {
              liveWebsocket.setError(null);
            } else {
              twilioGateway.setError(null);
            }
          }}
          onClearInfo={() => {
            if (routeMode === 'direct') {
              liveWebsocket.setInfo(null);
            } else {
              twilioGateway.setInfo(null);
            }
          }}
        />
      }
      main={
        <Stack gap={5}>
          <VoiceRouteSelector
            routeMode={routeMode}
            isAnySessionActive={isAnySessionActive}
            onChange={setRouteMode}
          />
          <Tile>
            <VoiceSessionSection
              clientIdentity={DEFAULT_IDENTITY}
              routeMode={routeMode}
              configLocked={configLocked}
              selectedPromptCode={selectedPromptCode}
              selectedPrompt={selectedPrompt}
              effectiveVoice={effectiveVoice}
              isPromptVoiceConfigured={isPromptVoiceConfigured}
              twilioMediaStreamVoiceOverride={twilioMediaStreamVoiceOverride}
              setTwilioMediaStreamVoiceOverride={setTwilioMediaStreamVoiceOverride}
              geminiVoiceCatalog={geminiVoiceCatalog}
              loadingGeminiVoices={loadingGeminiVoices}
              directSessionActive={directSessionActive}
              twilioSessionActive={twilioSessionActive}
              canDirectConnect={canDirectConnect}
              canDirectDisconnect={canDirectDisconnect}
              canDirectToggleMic={canDirectToggleMic}
              canDial={canDial}
              canHangup={canHangup}
              liveWebsocket={liveWebsocket}
              twilioGateway={twilioGateway}
            />
          </Tile>
          <VoiceLogsTile routeMode={routeMode} directLogs={directLogs} twilioLogs={twilioGateway.logs} />
        </Stack>
      }
      side={
        <VoiceSidePanel
          routeMode={routeMode}
          liveWebsocket={liveWebsocket}
          twilioGateway={twilioGateway}
          selectedPromptCode={selectedPromptCode}
          selectedPrompt={selectedPrompt}
          effectiveVoice={effectiveVoice}
          isPromptVoiceConfigured={isPromptVoiceConfigured}
          directDiagnostic={directDiagnostic}
          twilioDiagnostic={twilioDiagnostic}
        />
      }
    />
  );
}
