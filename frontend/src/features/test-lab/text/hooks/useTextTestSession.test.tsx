// @vitest-environment jsdom

import { useEffect } from 'react';
import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { UseUnifiedTestLabResult } from '../../../../hooks/unifiedTestLab/hookTypes';
import { useTextTestSession } from './useTextTestSession';

const mocks = vi.hoisted(() => ({
  startTestSession: vi.fn(),
  finalizeTestSession: vi.fn(),
  streamUnifiedChatResponse: vi.fn(),
  setSelectedPromptCode: vi.fn(),
  prompts: [
    {
      id: 'prompt-selected',
      name: 'Selected Prompt',
      code: 'selected_prompt',
      llmProvider: 'gemini',
      llmModel: 'gemini-2.5-flash',
      temperature: 0.4,
      maxTokens: 512,
      systemPrompt: 'selected system prompt',
      updatedAt: '2026-04-08T00:00:00Z',
      version: 1,
      isActive: true,
    },
    {
      id: 'prompt-bound',
      name: 'Bound Prompt',
      code: 'bound_prompt',
      llmProvider: 'openai',
      llmModel: 'gpt-4.1-mini',
      temperature: 0.4,
      maxTokens: 512,
      systemPrompt: 'bound system prompt',
      updatedAt: '2026-04-08T00:00:00Z',
      version: 1,
      isActive: true,
    },
  ],
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string, values?: Record<string, unknown>) =>
      typeof fallback === 'string'
        ? fallback.replace(/\{\{(\w+)\}\}/g, (_, token) => String(values?.[token] ?? ''))
        : key,
  }),
}));

vi.mock('../../../../hooks/usePromptTemplates', () => ({
  usePromptTemplates: () => ({
    prompts: mocks.prompts,
    loadingPrompts: false,
    selectedPromptCode: 'selected_prompt',
    setSelectedPromptCode: mocks.setSelectedPromptCode,
  }),
}));

vi.mock('../../../../api/testLab', () => ({
  startTestSession: mocks.startTestSession,
  finalizeTestSession: mocks.finalizeTestSession,
}));

vi.mock('../../../../hooks/unifiedTestLab/streaming', () => ({
  streamUnifiedChatResponse: mocks.streamUnifiedChatResponse,
}));

function buildSession(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    call_id: 'call-1',
    simulated_phone: '+819012345678',
    started_at: '2026-04-08T10:00:00+09:00',
    template_code: 'bound_prompt',
    llm_provider: 'openai',
    llm_model: 'gpt-4.1-mini',
    ...overrides,
  };
}

function buildFinalize(callId: string, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    call_id: callId,
    status: 'completed',
    ended_at: '2026-04-08T10:05:00+09:00',
    duration_seconds: 300,
    appointment_id: null,
    extraction: null,
    already_extracted: false,
    ...overrides,
  };
}

function HookHarness({ onValue }: { onValue: (value: UseUnifiedTestLabResult) => void }) {
  const value = useTextTestSession();

  useEffect(() => {
    onValue(value);
  }, [onValue, value]);

  return null;
}

function renderHookHarness() {
  let latest: UseUnifiedTestLabResult | null = null;
  render(<HookHarness onValue={(value) => void (latest = value)} />);
  return {
    get current() {
      if (!latest) {
        throw new Error('Hook value not ready');
      }
      return latest;
    },
  };
}

describe('useTextTestSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.prompts[0].llmModel = 'gemini-2.5-flash';
    mocks.streamUnifiedChatResponse.mockImplementation(
      async ({ onAssistantContent, onTokensUsed }: { onAssistantContent: (content: string) => void; onTokensUsed: (tokens: number) => void }) => {
        onAssistantContent('普通回复');
        onTokensUsed(7);
      }
    );
  });

  afterEach(() => {
    cleanup();
  });

  it('closes the previous session before starting a new one', async () => {
    mocks.startTestSession
      .mockResolvedValueOnce(buildSession({ call_id: 'call-1', template_code: 'bound_prompt' }))
      .mockResolvedValueOnce(buildSession({ call_id: 'call-2', template_code: 'bound_prompt_v2' }));
    mocks.finalizeTestSession.mockResolvedValue(buildFinalize('call-1'));

    const hook = renderHookHarness();

    await act(async () => {
      await hook.current.handleStartSession();
    });

    await waitFor(() => {
      expect(hook.current.session?.call_id).toBe('call-1');
    });

    await act(async () => {
      await hook.current.handleStartSession();
    });

    expect(mocks.finalizeTestSession).toHaveBeenCalledWith({
      call_id: 'call-1',
      template_code: 'bound_prompt',
      run_extraction: false,
    });

    await waitFor(() => {
      expect(hook.current.session?.call_id).toBe('call-2');
    });
  });

  it('blocks creating a text session when the selected prompt uses a live-only model', async () => {
    mocks.prompts[0].llmModel = 'gemini-2.5-flash-native-audio-latest';
    const harness = renderHookHarness();

    await act(async () => {
      await harness.current.handleStartSession();
    });

    expect(mocks.startTestSession).not.toHaveBeenCalled();
    expect(harness.current.error).toContain('live-only model');
  });

  it('finalizes the active session with extraction on manual finalize', async () => {
    mocks.startTestSession.mockResolvedValue(buildSession());
    mocks.finalizeTestSession.mockResolvedValue(
      buildFinalize('call-1', {
        appointment_id: 'appointment-1',
        extraction: {
          success: true,
          appointment_id: 'appointment-1',
          extracted_data: { category: '粗大ゴミ' },
          confidence: 0.95,
          message: '预约信息提取成功',
        },
      })
    );

    const hook = renderHookHarness();

    await act(async () => {
      await hook.current.handleStartSession();
    });

    await act(async () => {
      await hook.current.handleFinalize();
    });

    expect(mocks.finalizeTestSession).toHaveBeenCalledWith({
      call_id: 'call-1',
      template_code: 'bound_prompt',
      run_extraction: true,
    });

    await waitFor(() => {
      expect(hook.current.finalizeResult?.call_id).toBe('call-1');
      expect(hook.current.sessionClosed).toBe(true);
    });
  });

  it('closes the active session without extraction when clearing the panel', async () => {
    mocks.startTestSession.mockResolvedValue(buildSession());
    mocks.finalizeTestSession.mockResolvedValue(buildFinalize('call-1'));

    const hook = renderHookHarness();

    await act(async () => {
      await hook.current.handleStartSession();
    });

    await act(async () => {
      await hook.current.handleClear();
    });

    expect(mocks.finalizeTestSession).toHaveBeenCalledWith({
      call_id: 'call-1',
      template_code: 'bound_prompt',
      run_extraction: false,
    });

    await waitFor(() => {
      expect(hook.current.session).toBeNull();
      expect(hook.current.messages).toHaveLength(0);
      expect(hook.current.totalTokens).toBe(0);
    });
  });

  it('streams messages using the session-bound runtime returned by the backend', async () => {
    mocks.startTestSession.mockResolvedValue(buildSession());

    const hook = renderHookHarness();

    await act(async () => {
      await hook.current.handleSendMessage('你好');
    });

    expect(mocks.startTestSession).toHaveBeenCalledWith({
      template_code: 'selected_prompt',
      caller_name: 'Test Caller',
    });

    expect(mocks.streamUnifiedChatResponse).toHaveBeenCalledTimes(1);
    expect(mocks.streamUnifiedChatResponse.mock.calls[0][0]).toMatchObject({
      callId: 'call-1',
      templateCode: 'bound_prompt',
      provider: 'openai',
      model: 'gpt-4.1-mini',
      message: '你好',
    });

    await waitFor(() => {
      expect(hook.current.messages).toHaveLength(2);
      expect(hook.current.messages[1]?.content).toBe('普通回复');
      expect(hook.current.totalTokens).toBe(7);
    });
  });
});
