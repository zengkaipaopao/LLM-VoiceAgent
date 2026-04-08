import { describe, expect, it } from 'vitest';

import { resolveVoiceRouteTransition } from './routeMode';

describe('resolveVoiceRouteTransition', () => {
  it('disconnects the direct session when switching into twilio mode', () => {
    expect(resolveVoiceRouteTransition('direct', 'twilio')).toBe('disconnect_direct');
  });

  it('resets the twilio gateway when switching back to direct mode', () => {
    expect(resolveVoiceRouteTransition('twilio', 'direct')).toBe('reset_gateway');
  });

  it('does nothing when the route mode does not change', () => {
    expect(resolveVoiceRouteTransition('direct', 'direct')).toBe('noop');
    expect(resolveVoiceRouteTransition('twilio', 'twilio')).toBe('noop');
  });
});
