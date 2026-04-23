import type { VoiceRouteMode } from '../../../components/organisms/TestTabs/voice/types';

export type VoiceRouteTransitionAction = 'noop' | 'disconnect_direct' | 'reset_gateway';

export function resolveVoiceRouteTransition(
  previousMode: VoiceRouteMode,
  nextMode: VoiceRouteMode
): VoiceRouteTransitionAction {
  if (previousMode === nextMode) {
    return 'noop';
  }

  if (nextMode === 'direct') {
    return 'reset_gateway';
  }

  if (previousMode !== 'direct') {
    return 'reset_gateway';
  }

  return 'disconnect_direct';
}
