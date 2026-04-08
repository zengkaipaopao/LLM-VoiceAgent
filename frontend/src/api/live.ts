import { z } from 'zod';

import { http } from './http';

const LiveAuthTokenResponseSchema = z.object({
  auth_token: z.string(),
  model: z.string(),
  modalities: z.array(z.string()),
  voice: z.string().nullable().optional(),
  template_code: z.string().nullable().optional(),
  system_instruction: z.string().nullable().optional(),
  display_endpoint: z.string(),
});

export type LiveAuthTokenPayload = {
  model?: string;
  modalities?: string[];
  voice?: string;
  templateCode?: string;
  systemInstruction?: string;
};

export type LiveAuthTokenResponse = z.infer<typeof LiveAuthTokenResponseSchema>;

export async function fetchLiveAuthToken(
  payload: LiveAuthTokenPayload
): Promise<LiveAuthTokenResponse> {
  const response = await http.post('/live/auth-token', {
    model: payload.model,
    modalities: payload.modalities,
    voice: payload.voice,
    template_code: payload.templateCode,
    system_instruction: payload.systemInstruction,
  });

  return LiveAuthTokenResponseSchema.parse(response.data.data);
}
