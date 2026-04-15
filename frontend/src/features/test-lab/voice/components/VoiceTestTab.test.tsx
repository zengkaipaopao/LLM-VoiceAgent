// @vitest-environment jsdom

import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { VoiceTestTab } from './VoiceTestTab';

const mocks = vi.hoisted(() => ({
  useVoiceTestConsole: vi.fn(),
  useTwilioVoiceGateway: vi.fn(),
}));

vi.mock('../../../../components/molecules/TestTabs', () => ({
  TestWorkbenchShell: ({
    main,
    side,
    notice,
  }: {
    main: ReactNode;
    side: ReactNode;
    notice?: ReactNode;
  }) => (
    <div>
      <div data-testid="notice">{notice}</div>
      <div data-testid="main">{main}</div>
      <div data-testid="side">{side}</div>
    </div>
  ),
  TestTabNotifications: () => <div>notifications</div>,
}));

vi.mock('../../../../components/organisms/TestTabs/voice/VoiceRouteSelector', () => ({
  VoiceRouteSelector: ({
    onChange,
  }: {
    onChange: (mode: 'direct' | 'twilio') => void;
  }) => (
    <div>
      <button type="button" onClick={() => onChange('twilio')}>
        switch-twilio
      </button>
      <button type="button" onClick={() => onChange('direct')}>
        switch-direct
      </button>
    </div>
  ),
}));

vi.mock('../../../../components/organisms/TestTabs/voice/VoiceSessionSection', () => ({
  VoiceSessionSection: () => <div>voice-session</div>,
}));

vi.mock('../../../../components/organisms/TestTabs/voice/VoiceSidePanel', () => ({
  VoiceSidePanel: () => <div>voice-side-panel</div>,
}));

vi.mock('../../../../components/organisms/TestTabs/voice/VoiceLogsTile', () => ({
  VoiceLogsTile: () => <div>voice-logs</div>,
}));

vi.mock('../hooks/useVoiceTestConsole', () => ({
  useVoiceTestConsole: mocks.useVoiceTestConsole,
}));

vi.mock('../adapters/twilio/useTwilioVoiceGateway', () => ({
  useTwilioVoiceGateway: mocks.useTwilioVoiceGateway,
}));

function buildLiveWebsocket() {
  return {
    prompts: [
      {
        id: 'prompt-1',
        name: 'Prompt 1',
        code: 'base_appointment',
        llmProvider: 'gemini',
        llmModel: 'gemini-2.5-flash-native-audio-latest',
        temperature: 0.4,
        maxTokens: 512,
        systemPrompt: 'system prompt',
        voiceId: '',
        updatedAt: '2026-04-08T00:00:00Z',
        version: 1,
        isActive: true,
      },
    ],
    loadingPrompts: false,
    selectedPromptCode: 'base_appointment',
    setSelectedPromptCode: vi.fn(),
    micStatus: 'off',
    socketStatus: 'disconnected',
    logs: [],
    error: null,
    setError: vi.fn(),
    info: null,
    setInfo: vi.fn(),
    voice: '',
    model: 'gemini-2.5-flash-native-audio-latest',
    modalities: 'AUDIO',
    systemInstruction: 'system prompt',
    textInput: '',
    sessionId: '',
    assistantText: '',
    inputTranscript: '',
    outputTranscript: '',
    totalTokens: 0,
    displayWsUrl: 'Gemini Live client-to-server (ephemeral token, direct browser connection)',
    testCallId: 'call-1',
    finalizeResult: null,
    canUseRealtimeInput: false,
    voiceOnlyMode: true,
    connectSocket: vi.fn(),
    disconnectSocket: vi.fn(),
    clearConsole: vi.fn(),
    sendText: vi.fn(),
    toggleMicrophone: vi.fn(),
    setModel: vi.fn(),
    setModalities: vi.fn(),
    setVoice: vi.fn(),
    setSystemInstruction: vi.fn(),
    setTextInput: vi.fn(),
  };
}

function buildTwilioGateway() {
  return {
    capability: {
      configuredPhoneNumber: '+815012345678',
      geminiGenerateImplemented: true,
      geminiLiveImplemented: true,
      twilioWebcallImplemented: true,
    },
    voiceCatalog: {
      provider: 'Google',
      providers: ['Google', 'Amazon', 'ElevenLabs'],
      voices: ['Aoede'],
      source: 'cache',
      defaultVoice: 'Aoede',
      language: 'ja-JP',
    },
    loadingCapability: false,
    loadingVoices: false,
    targetNumber: '+815012345678',
    setTargetNumber: vi.fn(),
    targetNumberLocked: true,
    dialerStatus: 'idle',
    callStatus: 'idle',
    token: '',
    traceCallSid: '',
    traceSeq: 0,
    traceEvents: [],
    logs: [],
    info: null,
    error: null,
    setInfo: vi.fn(),
    setError: vi.fn(),
    refreshCapability: vi.fn(),
    refreshVoiceCatalog: vi.fn(),
    fetchToken: vi.fn(),
    registerDevice: vi.fn(),
    startDial: vi.fn(),
    prepareInboundCall: vi.fn(),
    hangupCall: vi.fn(),
    unregisterDevice: vi.fn(),
    resetGatewaySession: vi.fn(),
  };
}

describe('VoiceTestTab', () => {
  let liveWebsocket: ReturnType<typeof buildLiveWebsocket>;
  let twilioGateway: ReturnType<typeof buildTwilioGateway>;

  beforeEach(() => {
    liveWebsocket = buildLiveWebsocket();
    twilioGateway = buildTwilioGateway();
    mocks.useVoiceTestConsole.mockReturnValue(liveWebsocket);
    mocks.useTwilioVoiceGateway.mockReturnValue(twilioGateway);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('disconnects the direct route and bootstraps Twilio config when switching to twilio mode', async () => {
    render(<VoiceTestTab />);

    fireEvent.click(screen.getByText('switch-twilio'));

    await waitFor(() => {
      expect(liveWebsocket.disconnectSocket).toHaveBeenCalledTimes(1);
      expect(liveWebsocket.setError).toHaveBeenCalledWith(null);
      expect(twilioGateway.refreshCapability).toHaveBeenCalledTimes(1);
      expect(twilioGateway.refreshVoiceCatalog).toHaveBeenCalledTimes(1);
    });
  });

  it('resets the Twilio gateway when switching back to direct mode and only bootstraps once', async () => {
    render(<VoiceTestTab />);

    fireEvent.click(screen.getByText('switch-twilio'));
    await waitFor(() => {
      expect(twilioGateway.refreshCapability).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByText('switch-direct'));

    await waitFor(() => {
      expect(twilioGateway.resetGatewaySession).toHaveBeenCalledWith({ clearMessages: true });
    });

    fireEvent.click(screen.getByText('switch-twilio'));

    await waitFor(() => {
      expect(twilioGateway.refreshCapability).toHaveBeenCalledTimes(1);
      expect(twilioGateway.refreshVoiceCatalog).toHaveBeenCalledTimes(2);
      expect(liveWebsocket.disconnectSocket).toHaveBeenCalledTimes(2);
    });
  });
});
