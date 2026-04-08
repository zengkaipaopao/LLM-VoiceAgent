import { useCallback, useRef } from 'react';

import { LogLevel } from '../testTabs/eventLog';
import {
  OUTPUT_DEFAULT_SAMPLE_RATE,
  base64ToBytes,
  decodePcm16ToFloat32,
  getAudioContextCtor,
  parsePcmSampleRate,
} from './audioCodec';

interface UseRemoteAudioPlaybackOptions {
  pushLog: (level: LogLevel, message: string) => void;
}

interface UseRemoteAudioPlaybackResult {
  playPcmAudioChunk: (encodedData: string, mimeType?: string) => Promise<void>;
  isRemotePlaybackActive: () => boolean;
  resetRemotePlayback: () => void;
}

export function useRemoteAudioPlayback({
  pushLog,
}: UseRemoteAudioPlaybackOptions): UseRemoteAudioPlaybackResult {
  const remoteAudioContextRef = useRef<AudioContext | null>(null);
  const remotePlaybackCursorRef = useRef(0);

  const ensureRemoteAudioContext = useCallback(async (): Promise<AudioContext | null> => {
    const AudioContextCtor = getAudioContextCtor();
    if (!AudioContextCtor) return null;

    if (!remoteAudioContextRef.current) {
      remoteAudioContextRef.current = new AudioContextCtor({ sampleRate: OUTPUT_DEFAULT_SAMPLE_RATE });
      remotePlaybackCursorRef.current = 0;
    }

    const context = remoteAudioContextRef.current;
    if (context.state === 'suspended') {
      await context.resume();
    }
    return context;
  }, []);

  const playPcmAudioChunk = useCallback(
    async (encodedData: string, mimeType?: string) => {
      if (!encodedData) return;
      if (mimeType && !mimeType.toLowerCase().includes('audio/pcm')) {
        pushLog('warning', `Unsupported audio mime type: ${mimeType}`);
        return;
      }

      const context = await ensureRemoteAudioContext();
      if (!context) return;

      const bytes = base64ToBytes(encodedData);
      if (bytes.length < 2) return;

      const floatSamples = decodePcm16ToFloat32(bytes);
      const sampleRate = parsePcmSampleRate(mimeType, OUTPUT_DEFAULT_SAMPLE_RATE);
      const audioBuffer = context.createBuffer(1, floatSamples.length, sampleRate);
      const channelData = new Float32Array(floatSamples.length);
      channelData.set(floatSamples);
      audioBuffer.copyToChannel(channelData, 0);

      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);

      const now = context.currentTime + 0.01;
      const startAt = Math.max(remotePlaybackCursorRef.current, now);
      source.start(startAt);
      remotePlaybackCursorRef.current = startAt + audioBuffer.duration;
    },
    [ensureRemoteAudioContext, pushLog]
  );

  const isRemotePlaybackActive = useCallback((): boolean => {
    const context = remoteAudioContextRef.current;
    if (!context) {
      return false;
    }

    return remotePlaybackCursorRef.current > context.currentTime + 0.05;
  }, []);

  const resetRemotePlayback = useCallback(() => {
    if (remoteAudioContextRef.current) {
      void remoteAudioContextRef.current.close();
      remoteAudioContextRef.current = null;
    }
    remotePlaybackCursorRef.current = 0;
  }, []);

  return {
    playPcmAudioChunk,
    isRemotePlaybackActive,
    resetRemotePlayback,
  };
}
