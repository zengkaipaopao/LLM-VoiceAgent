import { useCallback, useRef, useState } from 'react';

import { LogLevel } from '../testTabs/eventLog';
import { MicStatus } from './types';
import {
  INPUT_TARGET_SAMPLE_RATE,
  float32ToPcm16Bytes,
  getAudioContextCtor,
  pcm16ToBase64,
  resampleFloat32,
} from './audioCodec';

interface UseMicrophoneStreamOptions {
  getWebSocket: () => WebSocket | null;
  sendLiveEvent: (payload: Record<string, unknown>) => void;
  pushLog: (level: LogLevel, message: string) => void;
  setError: (value: string | null) => void;
}

interface UseMicrophoneStreamResult {
  micStatus: MicStatus;
  startMicrophone: () => Promise<void>;
  stopMicrophone: () => void;
  resetMicrophone: () => void;
  toggleMicrophone: (enabled: boolean) => void;
  hasActiveMicrophoneResources: () => boolean;
}

export function useMicrophoneStream({
  getWebSocket,
  sendLiveEvent,
  pushLog,
  setError,
}: UseMicrophoneStreamOptions): UseMicrophoneStreamResult {
  const [micStatus, setMicStatus] = useState<MicStatus>('off');

  const localAudioContextRef = useRef<AudioContext | null>(null);
  const localSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  const hasActiveMicrophoneResources = useCallback(
    () => Boolean(processorRef.current || mediaStreamRef.current || localAudioContextRef.current),
    []
  );

  const releaseMicrophoneResources = useCallback(() => {
    const processor = processorRef.current;
    const source = localSourceRef.current;
    const gain = muteGainRef.current;
    const localContext = localAudioContextRef.current;
    const mediaStream = mediaStreamRef.current;

    if (processor) {
      processor.disconnect();
      processor.onaudioprocess = null;
      processorRef.current = null;
    }

    if (source) {
      source.disconnect();
      localSourceRef.current = null;
    }

    if (gain) {
      gain.disconnect();
      muteGainRef.current = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (localContext) {
      void localContext.close();
      localAudioContextRef.current = null;
    }
  }, []);

  const resetMicrophone = useCallback(() => {
    releaseMicrophoneResources();
    setMicStatus('off');
  }, [releaseMicrophoneResources]);

  const stopMicrophone = useCallback(() => {
    releaseMicrophoneResources();
    sendLiveEvent({ type: 'audio_end' });
    setMicStatus('off');
    pushLog('info', 'Microphone streaming stopped.');
  }, [pushLog, releaseMicrophoneResources, sendLiveEvent]);

  const startMicrophone = useCallback(async () => {
    if (micStatus !== 'off') return;

    const ws = getWebSocket();
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('Connect WebSocket before starting microphone.');
      return;
    }

    const AudioContextCtor = getAudioContextCtor();
    if (!AudioContextCtor) {
      setError('This browser does not support Web Audio API.');
      return;
    }

    setError(null);
    setMicStatus('starting');

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          noiseSuppression: true,
          echoCancellation: true,
        },
      });

      const audioContext = new AudioContextCtor();
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      const inputSampleRate = audioContext.sampleRate || INPUT_TARGET_SAMPLE_RATE;
      const source = audioContext.createMediaStreamSource(mediaStream);
      const processor = audioContext.createScriptProcessor(2048, 1, 1);
      const muteGain = audioContext.createGain();
      muteGain.gain.value = 0;

      pushLog('info', `Microphone sample rate: ${Math.round(inputSampleRate)} Hz`);

      processor.onaudioprocess = (event) => {
        const activeSocket = getWebSocket();
        if (!activeSocket || activeSocket.readyState !== WebSocket.OPEN) return;

        const input = event.inputBuffer.getChannelData(0);
        const normalized = resampleFloat32(input, inputSampleRate, INPUT_TARGET_SAMPLE_RATE);
        if (!normalized.length) return;

        const audioBytes = float32ToPcm16Bytes(normalized);
        activeSocket.send(
          JSON.stringify({
            type: 'audio_chunk',
            mime_type: `audio/pcm;rate=${INPUT_TARGET_SAMPLE_RATE}`,
            data: pcm16ToBase64(audioBytes),
          })
        );
      };

      source.connect(processor);
      processor.connect(muteGain);
      muteGain.connect(audioContext.destination);

      mediaStreamRef.current = mediaStream;
      localAudioContextRef.current = audioContext;
      localSourceRef.current = source;
      processorRef.current = processor;
      muteGainRef.current = muteGain;

      setMicStatus('on');
      pushLog('success', 'Microphone streaming started.');
    } catch (micError) {
      setMicStatus('off');
      setError(String(micError));
      pushLog('error', `Failed to start microphone: ${String(micError)}`);
    }
  }, [getWebSocket, micStatus, pushLog, setError]);

  const toggleMicrophone = useCallback(
    (enabled: boolean) => {
      if (enabled) {
        void startMicrophone();
        return;
      }

      if (micStatus !== 'off') {
        stopMicrophone();
      }
    },
    [micStatus, startMicrophone, stopMicrophone]
  );

  return {
    micStatus,
    startMicrophone,
    stopMicrophone,
    resetMicrophone,
    toggleMicrophone,
    hasActiveMicrophoneResources,
  };
}
