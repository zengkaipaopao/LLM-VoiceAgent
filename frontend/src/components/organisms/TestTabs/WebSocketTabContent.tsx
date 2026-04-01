import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Column,
  Grid,
  InlineLoading,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  Tag,
  TextArea,
  TextInput,
  Toggle,
  Tile,
} from '@carbon/react';

import { API_BASE_URL } from '../../../api/http';
import { fetchPrompts } from '../../../api/prompts';
import { PromptTemplate } from '../../../types/shared';
import styles from './WebSocketTabContent.module.scss';

type SocketStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
type MicStatus = 'off' | 'starting' | 'on';
type LogLevel = 'info' | 'success' | 'warning' | 'error';

interface EventLog {
  id: string;
  time: Date;
  level: LogLevel;
  message: string;
}

interface LiveEventPayload {
  type?: string;
  text?: string;
  message?: string;
  error?: string;
  data?: string;
  mime_type?: string;
  total_tokens?: number;
  session_id?: string;
  reason?: string | null;
}

const INPUT_TARGET_SAMPLE_RATE = 16000;
const OUTPUT_DEFAULT_SAMPLE_RATE = 24000;

function getAudioContextCtor(): typeof AudioContext | null {
  if (typeof window === 'undefined') return null;
  const ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  return ctor ?? null;
}

function pcm16ToBase64(pcmBytes: Uint8Array): string {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < pcmBytes.length; i += chunkSize) {
    const chunk = pcmBytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

function base64ToBytes(encoded: string): Uint8Array {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function decodePcm16ToFloat32(bytes: Uint8Array): Float32Array {
  const sampleCount = Math.floor(bytes.length / 2);
  const floatSamples = new Float32Array(sampleCount);
  for (let i = 0; i < sampleCount; i += 1) {
    const lo = bytes[i * 2];
    const hi = bytes[i * 2 + 1];
    let sample = (hi << 8) | lo;
    if (sample >= 0x8000) sample -= 0x10000;
    floatSamples[i] = sample / 32768;
  }
  return floatSamples;
}

function parsePcmSampleRate(mimeType: string | undefined, fallbackRate: number): number {
  if (!mimeType) return fallbackRate;
  const match = mimeType.toLowerCase().match(/rate=(\d{4,6})/);
  if (!match) return fallbackRate;
  const parsed = Number(match[1]);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallbackRate;
  return parsed;
}

function resampleFloat32(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (!input.length) return input;
  if (!Number.isFinite(inputRate) || !Number.isFinite(outputRate)) return input;
  if (inputRate <= 0 || outputRate <= 0) return input;
  if (inputRate === outputRate) return input;

  const outputLength = Math.max(1, Math.round((input.length * outputRate) / inputRate));
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i += 1) {
    const sourceIndex = (i * inputRate) / outputRate;
    const lower = Math.floor(sourceIndex);
    const upper = Math.min(input.length - 1, lower + 1);
    const alpha = sourceIndex - lower;
    output[i] = input[lower] * (1 - alpha) + input[upper] * alpha;
  }
  return output;
}

function float32ToPcm16Bytes(floatSamples: Float32Array): Uint8Array {
  const pcm16 = new Int16Array(floatSamples.length);
  for (let i = 0; i < floatSamples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatSamples[i]));
    pcm16[i] = sample < 0 ? sample * 32768 : sample * 32767;
  }
  return new Uint8Array(pcm16.buffer);
}

function toWebSocketBase(httpBaseUrl: string): string {
  if (httpBaseUrl.startsWith('https://')) return `wss://${httpBaseUrl.slice('https://'.length)}`;
  if (httpBaseUrl.startsWith('http://')) return `ws://${httpBaseUrl.slice('http://'.length)}`;
  return httpBaseUrl;
}

export function WebSocketTabContent() {
  const { t } = useTranslation(['pages']);

  const [socketStatus, setSocketStatus] = useState<SocketStatus>('disconnected');
  const [wsOpen, setWsOpen] = useState(false);
  const [micStatus, setMicStatus] = useState<MicStatus>('off');
  const [error, setError] = useState<string | null>(null);

  const [model, setModel] = useState('gemini-3.1-flash-live-preview');
  const [modalities, setModalities] = useState('AUDIO');
  const [voice, setVoice] = useState('');
  const [systemInstruction, setSystemInstruction] = useState(
    'You are a helpful bilingual voice assistant for customer service.'
  );
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [selectedPromptCode, setSelectedPromptCode] = useState('');
  const [textInput, setTextInput] = useState('');

  const [sessionId, setSessionId] = useState<string>('');
  const [assistantText, setAssistantText] = useState('');
  const [inputTranscript, setInputTranscript] = useState('');
  const [outputTranscript, setOutputTranscript] = useState('');
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [logs, setLogs] = useState<EventLog[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const localAudioContextRef = useRef<AudioContext | null>(null);
  const localSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  const remoteAudioContextRef = useRef<AudioContext | null>(null);
  const remotePlaybackCursorRef = useRef(0);

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((prev) => {
      const next = [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          time: new Date(),
          level,
          message,
        },
      ];
      return next.slice(-180);
    });
  }, []);

  const wsUrl = useMemo(() => {
    const base = toWebSocketBase(API_BASE_URL);
    const params = new URLSearchParams();
    if (model.trim()) params.set('model', model.trim());
    if (modalities.trim()) params.set('modalities', modalities.trim());
    if (voice.trim()) params.set('voice', voice.trim());
    if (selectedPromptCode.trim()) {
      params.set('template_code', selectedPromptCode.trim());
    } else if (systemInstruction.trim()) {
      params.set('system_instruction', systemInstruction.trim());
    }
    return `${base}/live/ws?${params.toString()}`;
  }, [model, modalities, voice, selectedPromptCode, systemInstruction]);

  const sendLiveEvent = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }, []);

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

  const canUseRealtimeInput = wsOpen;

  const handleLiveEvent = useCallback(
    async (event: LiveEventPayload) => {
      switch ((event.type || '').toLowerCase()) {
        case 'connected':
          setSocketStatus('connected');
          pushLog('success', 'Live gateway connected.');
          return;
        case 'session_ready':
          if (event.session_id) {
            setSessionId(event.session_id);
            pushLog('success', `Gemini Live session ready: ${event.session_id}`);
          }
          return;
        case 'text':
          if (event.text) {
            setAssistantText((prev) => prev + event.text);
          }
          return;
        case 'input_transcript':
          if (typeof event.text === 'string') {
            setInputTranscript(event.text);
          }
          return;
        case 'output_transcript':
          if (typeof event.text === 'string') {
            setOutputTranscript(event.text);
          }
          return;
        case 'audio_chunk':
          if (event.data) {
            await playPcmAudioChunk(event.data, event.mime_type);
          }
          return;
        case 'usage':
          if (typeof event.total_tokens === 'number') {
            setTotalTokens(event.total_tokens);
          }
          return;
        case 'turn_complete':
          setAssistantText((prev) => (prev.endsWith('\n') ? prev : `${prev}\n`));
          if (event.reason) {
            pushLog('info', `Turn complete: ${event.reason}`);
          } else {
            pushLog('info', 'Turn complete.');
          }
          return;
        case 'interrupted':
          pushLog('warning', 'Model response interrupted by activity.');
          return;
        case 'warning':
          pushLog('warning', event.message || 'Live warning');
          return;
        case 'error':
          setError(event.error || 'Live websocket error');
          setSocketStatus('error');
          pushLog('error', event.error || 'Live websocket error');
          return;
        default:
          return;
      }
    },
    [playPcmAudioChunk, pushLog]
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

  const connectSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    setError(null);
    setSocketStatus('connecting');
    setAssistantText('');
    setInputTranscript('');
    setOutputTranscript('');
    setTotalTokens(0);
    setSessionId('');
    setWsOpen(false);
    pushLog('info', `Connecting to ${wsUrl}`);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsOpen(true);
      setSocketStatus('connecting');
      pushLog('success', 'WebSocket connected. Waiting for Gemini Live session...');
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as LiveEventPayload;
        void handleLiveEvent(payload);
      } catch (parseError) {
        pushLog('warning', `Failed to parse message: ${String(parseError)}`);
      }
    };

    ws.onerror = () => {
      setSocketStatus('error');
      setError('WebSocket connection error.');
      pushLog('error', 'WebSocket connection error.');
    };

    ws.onclose = (event) => {
      setSocketStatus('disconnected');
      setWsOpen(false);
      const closeDetail = event.reason
        ? `WebSocket disconnected (code: ${event.code}, reason: ${event.reason}).`
        : `WebSocket disconnected (code: ${event.code}).`;
      pushLog('info', closeDetail);
      wsRef.current = null;
      if (processorRef.current || mediaStreamRef.current || localAudioContextRef.current) {
        releaseMicrophoneResources();
      }
      setMicStatus('off');
      setSessionId('');
      if (remoteAudioContextRef.current) {
        void remoteAudioContextRef.current.close();
        remoteAudioContextRef.current = null;
      }
      remotePlaybackCursorRef.current = 0;
    };
  }, [handleLiveEvent, pushLog, releaseMicrophoneResources, wsUrl]);

  const disconnectSocket = useCallback(() => {
    if (processorRef.current || mediaStreamRef.current || localAudioContextRef.current) {
      sendLiveEvent({ type: 'audio_end' });
      sendLiveEvent({ type: 'activity_end' });
      releaseMicrophoneResources();
      setMicStatus('off');
      pushLog('info', 'Microphone streaming stopped.');
    }
    sendLiveEvent({ type: 'close' });
    wsRef.current?.close();
    wsRef.current = null;
    setSocketStatus('disconnected');
    setWsOpen(false);
    setSessionId('');
    if (remoteAudioContextRef.current) {
      void remoteAudioContextRef.current.close();
      remoteAudioContextRef.current = null;
    }
    remotePlaybackCursorRef.current = 0;
  }, [pushLog, releaseMicrophoneResources, sendLiveEvent]);

  const sendText = useCallback(() => {
    const text = textInput.trim();
    if (!text) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket is not connected.');
      return;
    }
    sendLiveEvent({ type: 'text', text });
    pushLog('info', `Text input: ${text}`);
    setTextInput('');
  }, [pushLog, sendLiveEvent, textInput]);

  const stopMicrophone = useCallback(() => {
    releaseMicrophoneResources();

    sendLiveEvent({ type: 'audio_end' });
    sendLiveEvent({ type: 'activity_end' });

    setMicStatus('off');
    pushLog('info', 'Microphone streaming stopped.');
  }, [pushLog, releaseMicrophoneResources, sendLiveEvent]);

  const startMicrophone = useCallback(async () => {
    if (micStatus !== 'off') return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
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
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const input = event.inputBuffer.getChannelData(0);
        const normalized = resampleFloat32(input, inputSampleRate, INPUT_TARGET_SAMPLE_RATE);
        if (!normalized.length) return;
        const audioBytes = float32ToPcm16Bytes(normalized);
        ws.send(
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

      sendLiveEvent({ type: 'activity_start' });

      setMicStatus('on');
      pushLog('success', 'Microphone streaming started.');
    } catch (micError) {
      setMicStatus('off');
      setError(String(micError));
      pushLog('error', `Failed to start microphone: ${String(micError)}`);
    }
  }, [micStatus, pushLog, sendLiveEvent]);

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

  const clearConsole = useCallback(() => {
    setAssistantText('');
    setInputTranscript('');
    setOutputTranscript('');
    setLogs([]);
    setTotalTokens(0);
    setError(null);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadPrompts = async () => {
      setLoadingPrompts(true);
      try {
        const templates = await fetchPrompts();
        if (cancelled) return;
        setPrompts(templates);

        if (!templates.length) {
          setSelectedPromptCode('');
          return;
        }

        const preferred = templates.find((item) => item.code === 'general_appointment') ?? templates[0];
        setSelectedPromptCode(preferred.code);
      } catch (loadError) {
        if (cancelled) return;
        pushLog('error', `Failed to load prompts: ${String(loadError)}`);
      } finally {
        if (!cancelled) {
          setLoadingPrompts(false);
        }
      }
    };

    void loadPrompts();
    return () => {
      cancelled = true;
    };
  }, [pushLog]);

  useEffect(() => {
    if (!selectedPromptCode) return;
    const selected = prompts.find((item) => item.code === selectedPromptCode);
    if (!selected) return;
    setSystemInstruction(selected.systemPrompt || '');
    pushLog('info', `Loaded prompt template: ${selected.name} (${selected.code})`);
  }, [prompts, pushLog, selectedPromptCode]);

  useEffect(() => {
    return () => {
      if (processorRef.current || mediaStreamRef.current || localAudioContextRef.current) {
        stopMicrophone();
      }
      wsRef.current?.close();
      wsRef.current = null;
      if (remoteAudioContextRef.current) {
        void remoteAudioContextRef.current.close();
        remoteAudioContextRef.current = null;
      }
    };
  }, [stopMicrophone]);

  const statusTagType = useMemo(() => {
    if (socketStatus === 'connected') return 'green';
    if (socketStatus === 'connecting') return 'teal';
    if (socketStatus === 'error') return 'red';
    return 'cool-gray';
  }, [socketStatus]);

  const micTagType = useMemo(() => {
    if (micStatus === 'on') return 'green';
    if (micStatus === 'starting') return 'teal';
    return 'cool-gray';
  }, [micStatus]);

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {error && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            <InlineNotification
              kind="error"
              title={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
              subtitle={error}
              lowContrast
              onCloseButtonClick={() => setError(null)}
            />
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          <Tile className={styles.mainTile}>
            <div className={styles.header}>
              <div>
                <h3 className="cds--heading-03">
                  {t('pages:test.websocket.title', 'Gemini Live WebSocket Console')}
                </h3>
                <p className={styles.description}>
                  {t(
                    'pages:test.websocket.description',
                    'Connect to backend live gateway, stream mic audio, and inspect transcripts.'
                  )}
                </p>
              </div>
              <div className={styles.statusTags}>
                <Tag type={statusTagType}>{`Socket: ${socketStatus}`}</Tag>
                <Tag type={micTagType}>{`Mic: ${micStatus}`}</Tag>
              </div>
            </div>

            <Stack gap={6}>
              <div className={styles.formGrid}>
                {loadingPrompts ? (
                  <InlineLoading
                    description={t('pages:test.websocket.form.loadingPrompts', 'Loading prompts...')}
                  />
                ) : (
                  <Select
                    id="live-prompt-template"
                    labelText={t('pages:test.websocket.form.promptTemplate', 'Prompt Template')}
                    value={selectedPromptCode}
                    onChange={(event) => setSelectedPromptCode(event.target.value)}
                    disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                  >
                    <SelectItem
                      value=""
                      text={t('pages:test.websocket.form.noPrompt', 'No prompt (manual instruction)')}
                    />
                    {prompts.map((prompt) => (
                      <SelectItem
                        key={prompt.id}
                        value={prompt.code}
                        text={`${prompt.name} (${prompt.code})`}
                      />
                    ))}
                  </Select>
                )}

                <TextInput
                  id="live-model"
                  labelText={t('pages:test.websocket.form.model', 'Model')}
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                />

                <Select
                  id="live-modalities"
                  labelText={t('pages:test.websocket.form.modalities', 'Response Modalities')}
                  value={modalities}
                  onChange={(event) => setModalities(event.target.value)}
                  disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                >
                  <SelectItem value="AUDIO" text="AUDIO" />
                  <SelectItem value="TEXT" text="TEXT" />
                  <SelectItem value="AUDIO,TEXT" text="AUDIO + TEXT" />
                </Select>

                <TextInput
                  id="live-voice"
                  labelText={t('pages:test.websocket.form.voice', 'Voice (optional)')}
                  value={voice}
                  onChange={(event) => setVoice(event.target.value)}
                  disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                  placeholder="Aoede"
                />

                {!selectedPromptCode && (
                  <TextArea
                    id="live-system-instruction"
                    labelText={t('pages:test.websocket.form.systemInstruction', 'System Instruction')}
                    value={systemInstruction}
                    rows={3}
                    onChange={(event) => setSystemInstruction(event.target.value)}
                    disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                  />
                )}
              </div>

              <div className={styles.actions}>
                <div className={styles.actionButtons}>
                  <Button
                    size="sm"
                    kind="primary"
                    onClick={connectSocket}
                    disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
                  >
                    {t('pages:test.websocket.actions.connect', 'Connect')}
                  </Button>
                  <Button
                    size="sm"
                    kind="secondary"
                    onClick={disconnectSocket}
                    disabled={socketStatus === 'disconnected'}
                  >
                    {t('pages:test.websocket.actions.disconnect', 'Disconnect')}
                  </Button>
                  <Button size="sm" kind="ghost" onClick={clearConsole}>
                    {t('pages:test.websocket.actions.clear', 'Clear')}
                  </Button>
                </div>
                <Toggle
                  id="live-mic-toggle"
                  className={styles.micToggle}
                  size="sm"
                  labelA={t('pages:test.websocket.form.micOff', 'Mic Off')}
                  labelB={t('pages:test.websocket.form.micOn', 'Mic On')}
                  labelText={t('pages:test.websocket.form.micToggle', 'Microphone Input')}
                  toggled={micStatus !== 'off'}
                  disabled={!canUseRealtimeInput || micStatus === 'starting'}
                  onToggle={toggleMicrophone}
                />
              </div>

              <div className={styles.sendRow}>
                <TextInput
                  id="live-text-input"
                  labelText={t('pages:test.websocket.form.textInput', 'Realtime Text Input')}
                  value={textInput}
                  onChange={(event) => setTextInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      sendText();
                    }
                  }}
                  placeholder={t('pages:test.websocket.form.textPlaceholder', 'Type a realtime prompt')}
                  disabled={!canUseRealtimeInput}
                />
                <Button size="sm" kind="primary" onClick={sendText} disabled={!canUseRealtimeInput}>
                  {t('pages:test.websocket.actions.send', 'Send')}
                </Button>
              </div>

              <dl className={styles.metaList}>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.websocket.meta.sessionId', 'Session ID')}</dt>
                  <dd>{sessionId || '-'}</dd>
                </div>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.websocket.meta.tokens', 'Total Tokens')}</dt>
                  <dd>{totalTokens || 0}</dd>
                </div>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.websocket.meta.prompt', 'Prompt')}</dt>
                  <dd>{selectedPromptCode || '-'}</dd>
                </div>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.websocket.meta.endpoint', 'Endpoint')}</dt>
                  <dd>{wsUrl}</dd>
                </div>
              </dl>
            </Stack>
          </Tile>
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <Tile className={styles.panelTile}>
              <h4 className="cds--heading-01">
                {t('pages:test.websocket.sections.transcript', 'Realtime Transcripts')}
              </h4>
              <TextArea
                id="input-transcript"
                labelText={t('pages:test.websocket.sections.inputTranscript', 'Input Transcript')}
                rows={4}
                readOnly
                value={inputTranscript}
              />
              <TextArea
                id="output-transcript"
                labelText={t('pages:test.websocket.sections.outputTranscript', 'Output Transcript')}
                rows={4}
                readOnly
                value={outputTranscript}
              />
              <TextArea
                id="assistant-text"
                labelText={t('pages:test.websocket.sections.textOutput', 'Model Text Output')}
                rows={6}
                readOnly
                value={assistantText}
              />
            </Tile>

            <Tile className={styles.panelTile}>
              <h4 className="cds--heading-01">
                {t('pages:test.websocket.sections.logs', 'Event Logs')}
              </h4>
              <div className={styles.logPanel}>
                {logs.length === 0 ? (
                  <p className={styles.emptyLog}>
                    {t('pages:test.websocket.logs.empty', 'No logs yet. Connect and start a turn.')}
                  </p>
                ) : (
                  <ul className={styles.logList}>
                    {logs.map((log) => (
                      <li key={log.id} className={styles.logItem}>
                        <span className={styles.logTime}>
                          {log.time.toLocaleTimeString('ja-JP', { hour12: false })}
                        </span>
                        <span className={`${styles.logLevel} ${styles[`logLevel${log.level}`]}`}>
                          {log.level.toUpperCase()}
                        </span>
                        <span className={styles.logMessage}>{log.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Tile>
          </Stack>
        </Column>
      </Grid>
    </div>
  );
}
