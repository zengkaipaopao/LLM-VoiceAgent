import { useCallback, useRef } from 'react';

interface UseHeartbeatOptions {
  sendPing: () => void;
  intervalMs?: number;
}

interface UseHeartbeatResult {
  startHeartbeat: () => void;
  stopHeartbeat: () => void;
}

export function useHeartbeat({ sendPing, intervalMs = 10000 }: UseHeartbeatOptions): UseHeartbeatResult {
  const heartbeatTimerRef = useRef<number | null>(null);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current === null) return;
    window.clearInterval(heartbeatTimerRef.current);
    heartbeatTimerRef.current = null;
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatTimerRef.current = window.setInterval(() => {
      sendPing();
    }, intervalMs);
  }, [intervalMs, sendPing, stopHeartbeat]);

  return {
    startHeartbeat,
    stopHeartbeat,
  };
}
