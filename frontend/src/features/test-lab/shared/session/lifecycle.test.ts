import { describe, expect, it } from 'vitest';

import {
  getSessionCloseRequest,
  isTestSessionClosed,
  resolveTextStreamRuntime,
} from './lifecycle';

const activeSession = {
  call_id: 'call-1',
  simulated_phone: '+819012345678',
  started_at: '2026-04-08T10:00:00+09:00',
  template_code: 'base_appointment',
  llm_provider: 'gemini',
  llm_model: 'gemini-2.0-flash',
};

describe('test session lifecycle helpers', () => {
  it('detects when a session is already finalized', () => {
    expect(
      isTestSessionClosed(activeSession, {
        call_id: 'call-1',
        status: 'completed',
        ended_at: '2026-04-08T10:03:00+09:00',
        duration_seconds: 180,
        appointment_id: null,
        extraction: null,
        already_extracted: false,
      })
    ).toBe(true);

    expect(
      isTestSessionClosed(activeSession, {
        call_id: 'call-2',
        status: 'completed',
        ended_at: '2026-04-08T10:03:00+09:00',
        duration_seconds: 180,
        appointment_id: null,
        extraction: null,
        already_extracted: false,
      })
    ).toBe(false);
  });

  it('builds a non-extracting close request only for active sessions', () => {
    expect(getSessionCloseRequest(activeSession, null, 'fallback_prompt')).toEqual({
      call_id: 'call-1',
      template_code: 'base_appointment',
      run_extraction: false,
    });

    expect(
      getSessionCloseRequest(activeSession, {
        call_id: 'call-1',
        status: 'completed',
        ended_at: '2026-04-08T10:03:00+09:00',
        duration_seconds: 180,
        appointment_id: null,
        extraction: null,
        already_extracted: false,
      }, 'fallback_prompt')
    ).toBeNull();
  });

  it('keeps streaming bound to the session runtime instead of UI defaults', () => {
    expect(resolveTextStreamRuntime(activeSession, 'ignored_prompt')).toEqual({
      callId: 'call-1',
      templateCode: 'base_appointment',
      provider: 'gemini',
      model: 'gemini-2.0-flash',
    });
  });
});
