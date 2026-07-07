import { z } from 'zod';

import { http } from './http';

const UserSchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  display_name: z.string(),
  role: z.string(),
  auth_provider: z.string(),
});

const AuthSessionSchema = z.object({
  user: UserSchema,
  csrf_token: z.string(),
});

export type AuthenticatedUser = z.infer<typeof UserSchema>;

export async function login(username: string, password: string): Promise<AuthenticatedUser> {
  const response = await http.post('/auth/login', { username, password });
  return AuthSessionSchema.parse(response.data.data).user;
}

export async function getCurrentUser(): Promise<AuthenticatedUser> {
  const response = await http.get('/auth/me');
  return AuthSessionSchema.parse(response.data.data).user;
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout');
}
