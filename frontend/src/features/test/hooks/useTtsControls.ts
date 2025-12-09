import { RefObject, useCallback, useEffect, useRef, useState } from 'react';

import { synthesizeSpeech } from '../../../api/tts';
import { ttsProviderOptions, ttsModelOptions, openAiVoiceOptions, getGoogleVoices, googleLanguageOptions } from '../components/websocket/ttsConfig';
import { GoogleVoiceOption, TtsProviderOption } from '../components/websocket/ttsTypes';
import { base64ToBlob } from '../utils/audio';

type UseTtsControlsParams = {
  capabilityEnabled: boolean;
  initialVoice?: string;
};

export type TtsControls = {
  provider: TtsProviderOption['id'];
  setProvider: (provider: TtsProviderOption['id']) => void;
  language: string;
  setLanguage: (language: string) => void;
  model: string;
  setModel: (model: string) => void;
  voice: string;
  setVoice: (voice: string) => void;
  enabled: boolean;
  setEnabled: (value: boolean) => void;
  speakingRate: number;
  setSpeakingRate: (value: number) => void;
  pitch: number;
  setPitch: (value: number) => void;
  status: string | null;
  audioRef: RefObject<HTMLAudioElement>;
  controlsDisabled: boolean;
  providerOptions: typeof ttsProviderOptions;
  modelOptions: typeof ttsModelOptions[TtsProviderOption['id']];
  voiceOptions: GoogleVoiceOption[];
  languageOptions: typeof googleLanguageOptions;
  handleAssistantMessage: (text: string) => Promise<void>;
};

export function useTtsControls({ capabilityEnabled, initialVoice }: UseTtsControlsParams): TtsControls {
  const [provider, setProvider] = useState<TtsProviderOption['id']>('openai');
  const [model, setModel] = useState<string>(ttsModelOptions.openai[0].id);
  const [language, setLanguage] = useState<string>(googleLanguageOptions[0].code);
  const [voice, setVoice] = useState<string>(initialVoice ?? openAiVoiceOptions[0].id);
  const [enabled, setEnabled] = useState<boolean>(capabilityEnabled);
  const [speakingRate, setSpeakingRate] = useState<number>(1);
  const [pitch, setPitch] = useState<number>(0);
  const [status, setStatus] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  const controlsDisabled = !capabilityEnabled || !enabled;

  const cleanupAudio = useCallback(() => {
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const speakText = useCallback(
    async (text: string) => {
      if (!capabilityEnabled || !enabled || !text.trim()) return;
      setStatus('正在生成语音...');
      try {
        const result = await synthesizeSpeech({
          text,
          model,
          voice,
          provider,
          languageCode: provider === 'google' ? language : undefined,
          speakingRate: provider === 'google' ? speakingRate : undefined,
          pitch: provider === 'google' ? pitch : undefined,
        });
        cleanupAudio();
        const blob = base64ToBlob(result.audioBase64, result.contentType);
        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;
        setStatus('语音已生成，尝试播放...');
        const audio = audioRef.current;
        if (audio) {
          audio.src = url;
          const playPromise = audio.play();
          if (playPromise) {
            playPromise.catch((err) => {
              console.warn('自动播放受阻', err);
              setStatus('语音生成成功，请手动播放音频。');
            });
          }
        }
      } catch (error) {
        console.error('TTS 合成失败', error);
        setStatus('语音生成失败，请稍后再试。');
      }
    },
    [capabilityEnabled, cleanupAudio, enabled, language, model, pitch, provider, speakingRate, voice],
  );

  useEffect(() => cleanupAudio, [cleanupAudio]);

  useEffect(() => {
    setEnabled(capabilityEnabled);
  }, [capabilityEnabled]);

  useEffect(() => {
    setStatus(null);
  }, [enabled]);

  useEffect(() => {
    const options = ttsModelOptions[provider];
    setModel((prev) => (options.some((item) => item.id === prev) ? prev : options[0]?.id ?? prev));
  }, [provider]);

  useEffect(() => {
    if (provider === 'google') {
      const voices = getGoogleVoices(language);
      setVoice((prev) => (voices.some((item) => item.id === prev) ? prev : voices[0]?.id ?? prev));
    } else {
      setVoice((prev) => (openAiVoiceOptions.some((item) => item.id === prev) ? prev : openAiVoiceOptions[0].id));
    }
  }, [language, provider]);

  useEffect(() => {
    setSpeakingRate(1);
    setPitch(0);
  }, [provider]);

  useEffect(() => {
    return () => cleanupAudio();
  }, [cleanupAudio]);

  return {
    provider,
    setProvider,
    language,
    setLanguage,
    model,
    setModel,
    voice,
    setVoice,
    enabled,
    setEnabled,
    speakingRate,
    setSpeakingRate,
    pitch,
    setPitch,
    status,
    audioRef,
    controlsDisabled,
    providerOptions: ttsProviderOptions,
    modelOptions: ttsModelOptions[provider],
    voiceOptions: provider === 'google' ? getGoogleVoices(language) : openAiVoiceOptions,
    languageOptions: googleLanguageOptions,
    handleAssistantMessage: speakText,
  };
}
