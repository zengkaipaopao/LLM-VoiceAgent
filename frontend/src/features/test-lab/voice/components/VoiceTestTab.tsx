import { useEffect, useMemo, useRef, useState } from 'react';
import { Stack, Tile } from '@carbon/react';

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
import {
  useTwilioVoiceGateway,
  type UseTwilioVoiceGatewayResult,
} from '../adapters/twilio/useTwilioVoiceGateway';
import { useGeminiVoiceCatalog } from '../../../../hooks/useGeminiVoiceCatalog';
import { resolveVoiceRouteTransition } from '../routeMode';
import { useVoiceTestConsole } from '../hooks/useVoiceTestConsole';

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
  const liveWebsocket = useVoiceTestConsole();
  const twilioGateway = useTwilioVoiceGateway({ identity: DEFAULT_IDENTITY });
  const { voiceCatalog: geminiVoiceCatalog, loadingVoices: loadingGeminiVoices } =
    useGeminiVoiceCatalog();

  const [routeMode, setRouteMode] = useState<VoiceRouteMode>('direct');
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
    const directOverrideVoice = (liveWebsocket.voice || '').trim();
    if (routeMode === 'direct' && directOverrideVoice) return directOverrideVoice;
    const promptVoice = (selectedPrompt?.voiceId || '').trim();
    if (promptVoice) return promptVoice;
    return geminiVoiceCatalog.defaultVoice || twilioGateway.voiceCatalog.defaultVoice || 'Aoede';
  }, [
    geminiVoiceCatalog.defaultVoice,
    liveWebsocket.voice,
    routeMode,
    selectedPrompt?.voiceId,
    twilioGateway.voiceCatalog.defaultVoice,
  ]);

  const isPromptVoiceConfigured = Boolean((selectedPrompt?.voiceId || '').trim());

  useEffect(() => {
    if (routeMode !== 'twilio') {
      return;
    }
    if (twilioConfigBootstrappedRef.current) {
      return;
    }
    twilioConfigBootstrappedRef.current = true;
    void twilioGateway.refreshCapability();
    void twilioGateway.refreshVoiceCatalog();
  }, [routeMode, twilioGateway.refreshCapability, twilioGateway.refreshVoiceCatalog]);

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
      value: routeMode === 'direct' ? '浏览器直连 Gemini' : '电话网关接入（Twilio）',
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
      label: 'Gemini 音色',
      value: routeMode === 'direct' ? effectiveVoice || '默认' : effectiveVoice || '-',
      mono: true,
      tone: routeMode === 'twilio' && isPromptVoiceConfigured ? 'teal' : 'cool-gray',
    },
  ];

  const activeError = routeMode === 'direct' ? liveWebsocket.error : twilioGateway.error;
  const activeInfo = routeMode === 'direct' ? liveWebsocket.info : twilioGateway.info;
  const compatibilityWarning = useMemo(() => {
    const promptWarning = describeVoiceTabPromptModelWarning(
      selectedPrompt?.llmModel,
      selectedPromptCode
    );
    if (promptWarning) {
      return promptWarning;
    }
    if (routeMode === 'direct') {
      return describeVoiceTabOverrideWarning(liveWebsocket.model);
    }
    return null;
  }, [liveWebsocket.model, routeMode, selectedPrompt?.llmModel, selectedPromptCode]);
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
        />
      }
    />
  );
}
