import { RefObject } from 'react';
import { NumberInput, Select, SelectItem, Tile, Toggle } from '@carbon/react';

import { GoogleLanguageOption, TtsModelOption, TtsProviderOption } from './ttsTypes';

type TtsPanelProps = {
  capabilityEnabled: boolean;
  providerOptions: readonly TtsProviderOption[];
  provider: TtsProviderOption['id'];
  onProviderChange: (provider: TtsProviderOption['id']) => void;
  language: string;
  onLanguageChange: (language: string) => void;
  googleLanguages: GoogleLanguageOption[];
  enabled: boolean;
  onToggleEnabled: () => void;
  model: string;
  onModelChange: (model: string) => void;
  modelOptions: TtsModelOption[];
  voice: string;
  onVoiceChange: (voice: string) => void;
  voiceOptions: Array<{ id: string; label: string }>;
  speakingRate: number;
  onSpeakingRateChange: (value: number) => void;
  pitch: number;
  onPitchChange: (value: number) => void;
  status: string | null;
  controlsDisabled: boolean;
  audioRef: RefObject<HTMLAudioElement>;
};

export function TtsPanel({
  capabilityEnabled,
  providerOptions,
  provider,
  onProviderChange,
  language,
  onLanguageChange,
  googleLanguages,
  enabled,
  onToggleEnabled,
  model,
  onModelChange,
  modelOptions,
  voice,
  onVoiceChange,
  voiceOptions,
  speakingRate,
  onSpeakingRateChange,
  pitch,
  onPitchChange,
  status,
  controlsDisabled,
  audioRef,
}: TtsPanelProps) {
  return (
    <Tile className="session-panel">
      <div>
        <h3>语音配置</h3>
        <p className="session-panel__helper">
          {capabilityEnabled
            ? '这里仅控制文本转语音，聊天模型始终跟随 Prompt 设置。'
            : '当前 Prompt 未启用语音播报，可在 Prompt 管理中开启。'}
        </p>
      </div>
      <Select
        id="tts-provider-selector"
        labelText="TTS 服务商"
        value={provider}
        onChange={(event) => onProviderChange(event.target.value as TtsProviderOption['id'])}
        disabled={!capabilityEnabled}
      >
        {providerOptions.map((option) => (
          <SelectItem key={option.id} value={option.id} text={option.label} />
        ))}
      </Select>
      {provider === 'google' && (
        <Select
          id="tts-language-selector"
          labelText="语言"
          value={language}
          onChange={(event) => onLanguageChange(event.target.value)}
          disabled={controlsDisabled}
        >
          {googleLanguages.map((item) => (
            <SelectItem key={item.code} value={item.code} text={`${item.label} · ${item.code}`} />
          ))}
        </Select>
      )}
      <Toggle
        id="tts-enable-toggle"
        labelText="启用文本转语音"
        labelA="关闭"
        labelB="开启"
        toggled={enabled}
        onToggle={() => onToggleEnabled()}
        disabled={!capabilityEnabled}
      />
      <Select
        id="tts-model-selector"
        labelText="TTS 模型"
        value={model}
        onChange={(event) => onModelChange(event.target.value)}
        disabled={controlsDisabled}
      >
        {modelOptions.map((option) => (
          <SelectItem key={option.id} value={option.id} text={option.label} />
        ))}
      </Select>
      <Select
        id="tts-voice-selector"
        labelText="TTS 声音"
        value={voice}
        onChange={(event) => onVoiceChange(event.target.value)}
        disabled={controlsDisabled}
      >
        {voiceOptions.map((option) => (
          <SelectItem key={option.id} value={option.id} text={option.label} />
        ))}
      </Select>
      {provider === 'google' && (
        <>
          <NumberInput
            id="tts-speaking-rate"
            label="语速（0.25 ~ 4.0）"
            min={0.25}
            max={4}
            step={0.1}
            value={speakingRate}
            onChange={(_, { value }) => {
              const parsed = Number(value);
              if (!Number.isNaN(parsed)) {
                onSpeakingRateChange(Math.min(4, Math.max(0.25, parsed)));
              }
            }}
            disabled={controlsDisabled}
          />
          <NumberInput
            id="tts-pitch"
            label="音调（-20 ~ 20 半音）"
            min={-20}
            max={20}
            step={0.5}
            value={pitch}
            onChange={(_, { value }) => {
              const parsed = Number(value);
              if (!Number.isNaN(parsed)) {
                onPitchChange(Math.min(20, Math.max(-20, parsed)));
              }
            }}
            disabled={controlsDisabled}
          />
        </>
      )}
      <div className="tts-audio-panel">
        <p className="session-panel__helper">{status ?? '关闭后仅输出文本，启用后可试听语音。'}</p>
        <audio ref={audioRef} controls className="tts-audio-player" />
      </div>
    </Tile>
  );
}
