import type {
  FinalizeTestSessionRequest,
  FinalizeTestSessionResponse,
  StartTestSessionResponse,
} from '../../../../api/testLab';

export interface TextStreamRuntime {
  callId: string;
  templateCode: string;
  provider?: string;
  model?: string;
}

export function isTestSessionClosed(
  session: StartTestSessionResponse | null,
  finalizeResult: FinalizeTestSessionResponse | null
): boolean {
  return (
    !!session &&
    !!finalizeResult &&
    finalizeResult.call_id === session.call_id &&
    finalizeResult.status === 'completed'
  );
}

export function getSessionCloseRequest(
  session: StartTestSessionResponse | null,
  finalizeResult: FinalizeTestSessionResponse | null,
  fallbackTemplateCode: string
): FinalizeTestSessionRequest | null {
  if (!session || isTestSessionClosed(session, finalizeResult)) {
    return null;
  }

  return {
    call_id: session.call_id,
    template_code: session.template_code || fallbackTemplateCode,
    run_extraction: false,
  };
}

export function resolveTextStreamRuntime(
  session: StartTestSessionResponse,
  fallbackTemplateCode: string
): TextStreamRuntime {
  return {
    callId: session.call_id,
    templateCode: session.template_code || fallbackTemplateCode,
    provider: session.llm_provider,
    model: session.llm_model,
  };
}
