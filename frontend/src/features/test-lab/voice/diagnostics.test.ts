import { describe, expect, it } from 'vitest';

import {
  classifyDirectVoiceDiagnostic,
  classifyGatewayFallbackDiagnostic,
  mapBackendTraceDiagnostic,
} from './diagnostics';

describe('voice diagnostics', () => {
  it('classifies direct model incompatibility', () => {
    const diagnostic = classifyDirectVoiceDiagnostic({
      socketStatus: 'disconnected',
      micStatus: 'off',
      error: '当前模型不是 Gemini Live / Native Audio 模型。请在 Prompt 中选择语音模型。',
      logs: [],
      model: 'gemini-2.5-flash',
    });

    expect(diagnostic?.category).toBe('direct_model_configuration');
    expect(diagnostic?.status).toBe('error');
  });

  it('classifies twilio access token errors', () => {
    const diagnostic = classifyGatewayFallbackDiagnostic({
      error: 'Twilio Device 错误 AccessTokenInvalid (20101): Twilio was unable to validate your Access Token',
      dialerStatus: 'error',
      callStatus: 'idle',
      logs: [],
      traceEvents: [],
    });

    expect(diagnostic?.category).toBe('twilio_access_token');
    expect(diagnostic?.owner).toBe('twilio_credentials');
  });

  it('maps backend trace diagnostics to the shared frontend shape', () => {
    const diagnostic = mapBackendTraceDiagnostic({
      call_sid: 'CA123',
      status: 'error',
      category: 'google_vertex_permission',
      owner: 'google_cloud_iam',
      title: 'Vertex AI 调用权限不足',
      summary: 'permission denied',
      actions: ['检查服务账号角色'],
      evidence: [
        {
          seq: 10,
          ts: 123,
          type: 'stream_error',
          level: 'error',
          text: "Permission 'aiplatform.endpoints.predict' denied",
        },
      ],
      last_seq: 10,
      stream_active: false,
    });

    expect(diagnostic?.source).toBe('backend_trace');
    expect(diagnostic?.evidence[0]?.label).toBe('stream_error');
  });
});
