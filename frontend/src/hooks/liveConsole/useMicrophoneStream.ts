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
  canSendRealtimeInput: () => boolean;
  sendAudioChunk: (params: { mimeType: string; data: string }) => void;
  sendAudioStreamEnd: () => void;
  isRemotePlaybackActive: () => boolean;
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
  canSendRealtimeInput,
  sendAudioChunk,
  sendAudioStreamEnd,
  isRemotePlaybackActive,
  pushLog,
  setError,
}: UseMicrophoneStreamOptions): UseMicrophoneStreamResult {
  const [micStatus, setMicStatus] = useState<MicStatus>('off');

  const localAudioContextRef = useRef<AudioContext | null>(null);
  const localSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const playbackSuppressedRef = useRef(false);

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

    playbackSuppressedRef.current = false;
  }, []);

  const resetMicrophone = useCallback(() => {
    releaseMicrophoneResources();
    setMicStatus('off');
  }, [releaseMicrophoneResources]);

  const stopMicrophone = useCallback(() => {
    releaseMicrophoneResources();
    // Let Gemini Live keep turn detection ownership. Only close the stream when the user
    // explicitly turns the microphone off.
    sendAudioStreamEnd();
    setMicStatus('off');
    pushLog('info', 'Microphone streaming stopped.');
  }, [pushLog, releaseMicrophoneResources, sendAudioStreamEnd]);

  const startMicrophone = useCallback(async () => {
    if (micStatus !== 'off') return;

    if (!canSendRealtimeInput()) {
      setError('Connect Gemini Live before starting microphone.');
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
        if (!canSendRealtimeInput()) return;

        if (isRemotePlaybackActive()) {
          if (!playbackSuppressedRef.current) {
            playbackSuppressedRef.current = true;
            pushLog('info', 'Microphone uplink paused while AI audio is playing.');
          }
          return;
        }

        if (playbackSuppressedRef.current) {
          playbackSuppressedRef.current = false;
          pushLog('info', 'Microphone uplink resumed.');
        }

        const input = event.inputBuffer.getChannelData(0);
        const normalized = resampleFloat32(input, inputSampleRate, INPUT_TARGET_SAMPLE_RATE);
        if (!normalized.length) return;

        const audioBytes = float32ToPcm16Bytes(normalized);

        sendAudioChunk({
          mimeType: `audio/pcm;rate=${INPUT_TARGET_SAMPLE_RATE}`,
          data: pcm16ToBase64(audioBytes),
        });
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
  }, [canSendRealtimeInput, isRemotePlaybackActive, micStatus, pushLog, sendAudioChunk, setError]);

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
