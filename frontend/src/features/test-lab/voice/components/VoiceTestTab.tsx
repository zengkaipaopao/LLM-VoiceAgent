import { useEffect, useMemo, useRef, useState } from 'react';
import { Stack, Tile } from '@carbon/react';

import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../../../components/molecules/TestTabs';
import {
  describeTwilioTabPromptModelWarning,
  describeVoiceTabOverrideWarning,
  describeVoiceTabPromptModelWarning,
} from '../../../../config/llmModels';
import { VoiceLogsTile } from '../../../../components/organisms/TestTabs/voice/VoiceLogsTile';
import { VoiceRouteSelector } from '../../../../components/organisms/TestTabs/voice/VoiceRouteSelector';
import { VoiceSessionSection } from '../../../../components/organisms/TestTabs/voice/VoiceSessionSection';
import { VoiceSidePanel } from '../../../../components/organisms/TestTabs/voice/VoiceSidePanel';
import type { VoiceRouteMode } from '../../../../components/organisms/TestTabs/voice/types';
import {
  useTwilioVoiceGateway,
  type TwilioTransportMode,
  type TwilioTtsProvider,
  type UseTwilioVoiceGatewayResult,
} from '../adapters/twilio/useTwilioVoiceGateway';
import { useGeminiVoiceCatalog } from '../../../../hooks/useGeminiVoiceCatalog';
import { resolveVoiceRouteTransition } from '../routeMode';
import { matchGeminiLiveVoice, resolveGeminiLiveVoice } from '../voiceSelection';
import { useVoiceTestConsole } from '../hooks/useVoiceTestConsole';

const DEFAULT_IDENTITY = 'webcall-tester';
const TWILIO_PINNED_VOICE_IDS: Partial<Record<TwilioTtsProvider, string[]>> = {
  ElevenLabs: ['jqcCZkN6Knx8BJ5TBdYR', 'UgBBYS2sOqTuMpoF3BR0'],
};

function resolveTwilioOfficialVoice(
  value: string | null | undefined,
  officialVoices: string[],
  provider: TwilioTtsProvider
): string | null {
  const token = (value || '').trim();
  if (!token) return null;

  let candidate = token;
  if (provider === 'Google' && candidate.startsWith('Google.')) {
    candidate = candidate.slice('Google.'.length).trim();
  }
  if (provider === 'Amazon' && candidate.startsWith('Amazon.')) {
    candidate = candidate.slice('Amazon.'.length).trim();
  }
  if (provider === 'ElevenLabs' && candidate.startsWith('ElevenLabs.')) {
    candidate = candidate.slice('ElevenLabs.'.length).trim();
  }
  const chirpMarker = '-Chirp3-HD-';
  if (provider === 'Google' && candidate.includes(chirpMarker)) {
    candidate = candidate.split(chirpMarker)[1]?.trim() || candidate;
  }

  const lowered = candidate.toLowerCase();
  const matched = officialVoices.find((voice) => {
    const trimmedVoice = voice.trim();
    if (trimmedVoice.toLowerCase() === lowered) {
      return true;
    }
    if (provider === 'Google' && trimmedVoice.toLowerCase().endsWith(`-chirp3-hd-${lowered}`)) {
      return true;
    }
    return false;
  });
  return matched ?? null;
}

function resolveTwilioVoiceOverride(
  value: string | null | undefined,
  officialVoices: string[],
  provider: TwilioTtsProvider
): string | null {
  const token = (value || '').trim();
  if (!token) return null;
  return resolveTwilioOfficialVoice(token, officialVoices, provider) ?? token;
}

function normalizeTwilioTtsProvider(value: string | null | undefined): TwilioTtsProvider | null {
  const token = (value || '').trim().toLowerCase();
  if (!token) return null;
  if (token === 'google' || token === 'gemini') return 'Google';
  if (token === 'amazon' || token === 'amazonpolly' || token === 'amazon_polly') return 'Amazon';
  if (token === 'elevenlabs') return 'ElevenLabs';
  return null;
}

function resolvePromptTwilioTtsProvider(prompt: { voiceProvider?: string; voiceId?: string } | undefined): TwilioTtsProvider | null {
  const explicitProvider = normalizeTwilioTtsProvider(prompt?.voiceProvider);
  if (explicitProvider) return explicitProvider;

  const voiceToken = (prompt?.voiceId || '').trim();
  if (!voiceToken) return null;
  if (voiceToken.includes('-Chirp3-HD-') || voiceToken.startsWith('Google.')) return 'Google';
  if (voiceToken.startsWith('Amazon.')) return 'Amazon';
  if (/^[A-Za-z0-9]{20}(?:-[A-Za-z0-9_.]+)?(?:-[0-9.]+(?:_[0-9.]+){2})?$/.test(voiceToken)) {
    return 'ElevenLabs';
  }
  return null;
}

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
  const liveWebsocket = useVoiceTestConsole();
  const twilioGateway = useTwilioVoiceGateway({ identity: DEFAULT_IDENTITY });
  const { voiceCatalog: geminiVoiceCatalog, loadingVoices: loadingGeminiVoices } =
    useGeminiVoiceCatalog();

  const [routeMode, setRouteMode] = useState<VoiceRouteMode>('direct');
  const [twilioTransportMode, setTwilioTransportMode] =
    useState<TwilioTransportMode>('conversationrelay');
  const [twilioTtsProvider, setTwilioTtsProvider] = useState<TwilioTtsProvider | ''>('');
  const [twilioVoiceOverride, setTwilioVoiceOverride] = useState('');
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
  const promptTwilioTtsProvider = useMemo(
    () => resolvePromptTwilioTtsProvider(selectedPrompt),
    [selectedPrompt]
  );
  const effectiveTwilioTtsProvider = useMemo<TwilioTtsProvider>(
    () => normalizeTwilioTtsProvider(twilioTtsProvider) || promptTwilioTtsProvider || 'ElevenLabs',
    [promptTwilioTtsProvider, twilioTtsProvider]
  );
  const twilioVoiceOptions = useMemo(() => {
    const pinned = TWILIO_PINNED_VOICE_IDS[effectiveTwilioTtsProvider] || [];
    return [...new Set([...pinned, ...twilioGateway.voiceCatalog.voices])];
  }, [effectiveTwilioTtsProvider, twilioGateway.voiceCatalog.voices]);

  const twilioPromptVoice = useMemo(
    () =>
      promptTwilioTtsProvider === effectiveTwilioTtsProvider
        ? resolveTwilioOfficialVoice(
            selectedPrompt?.voiceId,
            twilioVoiceOptions,
            effectiveTwilioTtsProvider
          )
        : null,
    [
      effectiveTwilioTtsProvider,
      promptTwilioTtsProvider,
      selectedPrompt?.voiceId,
      twilioVoiceOptions,
    ]
  );
  const twilioVoicePreset = useMemo(
    () =>
      resolveTwilioOfficialVoice(
        twilioVoiceOverride,
        twilioVoiceOptions,
        effectiveTwilioTtsProvider
      ) || '',
    [
      effectiveTwilioTtsProvider,
      twilioVoiceOptions,
      twilioVoiceOverride,
    ]
  );
  const effectiveVoice = useMemo(() => {
    const directOverrideVoice = (liveWebsocket.voice || '').trim();
    if (routeMode === 'direct' && directOverrideVoice) return directOverrideVoice;
    if (routeMode === 'twilio') {
      if (twilioTransportMode === 'media_stream_live') {
        const supportedGeminiVoices = geminiVoiceCatalog.voices;
        const defaultGeminiVoice = geminiVoiceCatalog.defaultVoice || 'Aoede';
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
      }
      const overrideVoice = resolveTwilioVoiceOverride(
        twilioVoiceOverride,
        twilioVoiceOptions,
        effectiveTwilioTtsProvider
      );
      if (overrideVoice) return overrideVoice;
      if (twilioPromptVoice) return twilioPromptVoice;
      return twilioGateway.voiceCatalog.defaultVoice || '';
    }
    const promptVoice = (selectedPrompt?.voiceId || '').trim();
    if (promptVoice) return promptVoice;
    return geminiVoiceCatalog.defaultVoice || twilioGateway.voiceCatalog.defaultVoice || 'Aoede';
  }, [
    geminiVoiceCatalog.voices,
    geminiVoiceCatalog.defaultVoice,
    liveWebsocket.voice,
    routeMode,
    selectedPrompt?.voiceId,
    selectedPrompt?.voiceProvider,
    twilioTransportMode,
    twilioVoiceOptions,
    twilioGateway.voiceCatalog.defaultVoice,
    effectiveTwilioTtsProvider,
    twilioMediaStreamVoiceOverride,
    twilioPromptVoice,
    twilioVoiceOverride,
  ]);
  const isPromptVoiceConfigured =
    routeMode === 'twilio'
      ? twilioTransportMode === 'media_stream_live'
        ? Boolean(
            matchGeminiLiveVoice(selectedPrompt?.voiceId, {
              voiceProvider: selectedPrompt?.voiceProvider,
              supportedVoices: geminiVoiceCatalog.voices,
            })
          )
        : Boolean(twilioPromptVoice)
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
    if (routeMode !== 'twilio') {
      return;
    }
    if (twilioTransportMode !== 'conversationrelay') {
      return;
    }
    void twilioGateway.refreshVoiceCatalog({ provider: effectiveTwilioTtsProvider });
  }, [
    effectiveTwilioTtsProvider,
    routeMode,
    twilioGateway.refreshVoiceCatalog,
    twilioTransportMode,
  ]);

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
      label: '测试目标',
      value: '语音连通性',
      tone: 'teal',
    },
    {
      id: 'route',
      label: '接入方式',
      value:
        routeMode === 'direct'
          ? '浏览器直连 Gemini'
          : twilioTransportMode === 'conversationrelay'
            ? '电话网关（ConversationRelay）'
            : '电话网关（Media Streams）',
      tone: 'teal',
    },
    {
      id: 'connection',
      label: '连接状态',
      value: routeMode === 'direct' ? liveWebsocket.socketStatus : twilioGateway.callStatus,
      tone: routeMode === 'direct' ? directSocketTone : toCallTone(twilioGateway.callStatus),
      mono: true,
    },
    {
      id: 'audio',
      label: '音频采集',
      value: routeMode === 'direct' ? liveWebsocket.micStatus : twilioGateway.dialerStatus,
      tone: routeMode === 'direct' ? directMicTone : toDialerTone(twilioGateway.dialerStatus),
      mono: true,
    },
    {
      id: 'prompt',
      label: 'Prompt',
      value: selectedPromptCode || '-',
      mono: true,
    },
    {
      id: 'voice',
      label:
        routeMode === 'direct'
          ? 'Gemini 音色'
          : twilioTransportMode === 'conversationrelay'
            ? '电话音色'
            : 'Gemini 音色',
      value: routeMode === 'direct' ? effectiveVoice || '默认' : effectiveVoice || '-',
      mono: true,
      tone: routeMode === 'twilio' && isPromptVoiceConfigured ? 'teal' : 'cool-gray',
    },
    ...(routeMode === 'twilio' && twilioTransportMode === 'conversationrelay'
      ? ([
          {
            id: 'tts-provider',
            label: '电话语音层',
            value: effectiveTwilioTtsProvider,
            mono: true,
            tone: 'teal' as const,
          },
        ] satisfies TestWorkbenchSummaryItem[])
      : []),
  ];

  const activeError = routeMode === 'direct' ? liveWebsocket.error : twilioGateway.error;
  const activeInfo = routeMode === 'direct' ? liveWebsocket.info : twilioGateway.info;
  const compatibilityWarning = useMemo(() => {
    const promptWarning =
      routeMode === 'direct'
        ? describeVoiceTabPromptModelWarning(selectedPrompt?.llmModel, selectedPromptCode)
        : twilioTransportMode === 'conversationrelay'
          ? describeTwilioTabPromptModelWarning(selectedPrompt?.llmModel, selectedPromptCode)
          : describeVoiceTabPromptModelWarning(selectedPrompt?.llmModel, selectedPromptCode);
    if (promptWarning) {
      return promptWarning;
    }
    if (routeMode === 'direct') {
      return describeVoiceTabOverrideWarning(liveWebsocket.model);
    }
    return null;
  }, [
    liveWebsocket.model,
    routeMode,
    selectedPrompt?.llmModel,
    selectedPromptCode,
    twilioTransportMode,
  ]);
  const directLogs = useMemo(() => [...liveWebsocket.logs].slice(-180).reverse(), [liveWebsocket.logs]);

  return (
    <TestWorkbenchShell
      title="语音连通性测试台"
      description="统一验证 Gemini 语音会话是否可建立、可收音、可转写、可回复。"
      summaryItems={summaryItems}
      notice={
        <TestTabNotifications
          error={activeError}
          info={activeInfo}
          warning={compatibilityWarning}
          errorTitle="请求失败"
          successTitle="执行成功"
          warningTitle="配置提示"
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
              twilioTransportMode={twilioTransportMode}
              setTwilioTransportMode={setTwilioTransportMode}
              twilioTtsProvider={effectiveTwilioTtsProvider}
              setTwilioTtsProvider={setTwilioTtsProvider}
              twilioVoiceOptions={twilioVoiceOptions}
              twilioVoicePreset={twilioVoicePreset}
              twilioVoiceOverride={twilioVoiceOverride}
              setTwilioVoiceOverride={setTwilioVoiceOverride}
              twilioMediaStreamVoiceOverride={twilioMediaStreamVoiceOverride}
              setTwilioMediaStreamVoiceOverride={setTwilioMediaStreamVoiceOverride}
              promptVoiceSupportedByTwilio={Boolean(twilioPromptVoice)}
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
          isPromptVoiceConfigured={isPromptVoiceConfigured}
          twilioTransportMode={twilioTransportMode}
          twilioTtsProvider={effectiveTwilioTtsProvider}
        />
      }
    />
  );
}
