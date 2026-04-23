import { describe, expect, it } from 'vitest';

import { resolveVoiceRouteTransition } from './routeMode';

describe('resolveVoiceRouteTransition', () => {
  it('disconnects the direct session when switching into twilio mode', () => {
    expect(resolveVoiceRouteTransition('direct', 'twilio_official')).toBe('disconnect_direct');
    expect(resolveVoiceRouteTransition('direct', 'twilio_media_stream')).toBe(
      'disconnect_direct'
    );
  });

  it('resets the twilio gateway when switching back to direct mode', () => {
    expect(resolveVoiceRouteTransition('twilio_official', 'direct')).toBe('reset_gateway');
    expect(resolveVoiceRouteTransition('twilio_media_stream', 'direct')).toBe('reset_gateway');
  });

  it('resets the twilio gateway when switching between twilio implementations', () => {
    expect(resolveVoiceRouteTransition('twilio_official', 'twilio_media_stream')).toBe(
      'reset_gateway'
    );
    expect(resolveVoiceRouteTransition('twilio_media_stream', 'twilio_official')).toBe(
      'reset_gateway'
    );
  });

  it('does nothing when the route mode does not change', () => {
    expect(resolveVoiceRouteTransition('direct', 'direct')).toBe('noop');
    expect(resolveVoiceRouteTransition('twilio_official', 'twilio_official')).toBe('noop');
    expect(resolveVoiceRouteTransition('twilio_media_stream', 'twilio_media_stream')).toBe(
      'noop'
    );
  });
});
