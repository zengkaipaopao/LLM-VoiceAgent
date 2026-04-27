import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, InlineLoading, Tag, Tile, Toggle } from '@carbon/react';

import {
  evaluateVoiceAudioLab,
  prepareVoiceAudioLab,
  type VoiceAudioLabEvaluation,
  type VoiceAudioLabVariant,
} from '../../../../api/voiceAudioLab';
import styles from '../TwilioTabContent.module.scss';
import {
  INPUT_TARGET_SAMPLE_RATE,
  float32ToPcm16Bytes,
  getAudioContextCtor,
  pcm16ToBase64,
  resampleFloat32,
} from '../../../../hooks/liveConsole/audioCodec';

type AudioLabRecordStatus = 'idle' | 'requesting' | 'recording' | 'preparing';

interface VoiceAudioLabTileProps {
  promptCode: string;
  voiceName?: string;
}

function concatUint8Arrays(chunks: Uint8Array[]): Uint8Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
  const merged = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return merged;
}

function formatDuration(durationMs: number): string {
  if (!Number.isFinite(durationMs) || durationMs <= 0) return '0.0s';
  return `${(durationMs / 1000).toFixed(durationMs >= 10_000 ? 0 : 1)}s`;
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function resolveEvaluationTranscript(finalText: string, partials: string[]): string {
  const finalValue = finalText.trim();
  if (finalValue) {
    return finalValue;
  }
  const normalizedPartials = partials.map((item) => item.trim()).filter(Boolean);
  if (!normalizedPartials.length) {
    return '';
  }
  return normalizedPartials.join('');
}

export function VoiceAudioLabTile({ promptCode, voiceName }: VoiceAudioLabTileProps) {
  const [recordStatus, setRecordStatus] = useState<AudioLabRecordStatus>('idle');
  const [recordedDurationMs, setRecordedDurationMs] = useState(0);
  const [variants, setVariants] = useState<VoiceAudioLabVariant[]>([]);
  const [evaluations, setEvaluations] = useState<Record<string, VoiceAudioLabEvaluation | undefined>>({});
  const [evaluatingVariantId, setEvaluatingVariantId] = useState<string | null>(null);
  const [openingAlreadyPlayed, setOpeningAlreadyPlayed] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const pcmChunksRef = useRef<Uint8Array[]>([]);
  const inputSampleRateRef = useRef(INPUT_TARGET_SAMPLE_RATE);
  const durationUpdateAtRef = useRef(0);

  const hasRecording = variants.length > 0;

  const releaseRecordingResources = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (muteGainRef.current) {
      muteGainRef.current.disconnect();
      muteGainRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      releaseRecordingResources();
    };
  }, [releaseRecordingResources]);

  const stopRecording = useCallback(async () => {
    if (recordStatus !== 'recording' && recordStatus !== 'requesting') {
      return;
    }

    releaseRecordingResources();
    const mergedPcm = concatUint8Arrays(pcmChunksRef.current);
    pcmChunksRef.current = [];

    if (!mergedPcm.byteLength) {
      setRecordStatus('idle');
      setRecordedDurationMs(0);
      setError('录音为空，请重新录一段后再试。');
      return;
    }

    setRecordStatus('preparing');
    setError(null);
    setInfo(null);
    setEvaluations({});

    try {
      const prepared = await prepareVoiceAudioLab({
        audioBase64: pcm16ToBase64(mergedPcm),
        sampleRate: INPUT_TARGET_SAMPLE_RATE,
      });
      setVariants(prepared.variants);
      setRecordedDurationMs(prepared.variants[0]?.durationMs ?? 0);
      setInfo('三种离线音频版本已生成，可以分别回放并送 Gemini Live 验证。');
    } catch (prepareError) {
      const message = prepareError instanceof Error ? prepareError.message : String(prepareError);
      setError(`生成离线音频版本失败: ${message}`);
      setVariants([]);
    } finally {
      setRecordStatus('idle');
    }
  }, [recordStatus, releaseRecordingResources]);

  const startRecording = useCallback(async () => {
    if (recordStatus !== 'idle') {
      return;
    }

    const AudioContextCtor = getAudioContextCtor();
    if (!AudioContextCtor) {
      setError('当前浏览器不支持 Web Audio API。');
      return;
    }

    setError(null);
    setInfo(null);
    setVariants([]);
    setEvaluations({});
    setRecordedDurationMs(0);
    pcmChunksRef.current = [];
    durationUpdateAtRef.current = 0;
    setRecordStatus('requesting');

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          noiseSuppression: true,
          echoCancellation: true,
          autoGainControl: true,
        },
      });

      const audioContext = new AudioContextCtor();
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      const inputSampleRate = audioContext.sampleRate || INPUT_TARGET_SAMPLE_RATE;
      inputSampleRateRef.current = inputSampleRate;

      const source = audioContext.createMediaStreamSource(mediaStream);
      const processor = audioContext.createScriptProcessor(2048, 1, 1);
      const muteGain = audioContext.createGain();
      muteGain.gain.value = 0;

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        const normalized = resampleFloat32(input, inputSampleRateRef.current, INPUT_TARGET_SAMPLE_RATE);
        if (!normalized.length) {
          return;
        }
        const pcmBytes = float32ToPcm16Bytes(normalized);
        const chunk = new Uint8Array(pcmBytes);
        pcmChunksRef.current.push(chunk);

        const now = performance.now();
        if (now - durationUpdateAtRef.current >= 180) {
          durationUpdateAtRef.current = now;
          const totalBytes = pcmChunksRef.current.reduce((sum, item) => sum + item.byteLength, 0);
          setRecordedDurationMs(Math.round((totalBytes * 1000) / (INPUT_TARGET_SAMPLE_RATE * 2)));
        }
      };

      source.connect(processor);
      processor.connect(muteGain);
      muteGain.connect(audioContext.destination);

      audioContextRef.current = audioContext;
      mediaStreamRef.current = mediaStream;
      sourceRef.current = source;
      processorRef.current = processor;
      muteGainRef.current = muteGain;

      setRecordStatus('recording');
    } catch (recordError) {
      releaseRecordingResources();
      const message = recordError instanceof Error ? recordError.message : String(recordError);
      setError(`开始录音失败: ${message}`);
      setRecordStatus('idle');
    }
  }, [recordStatus, releaseRecordingResources]);

  const resetLab = useCallback(() => {
    releaseRecordingResources();
    pcmChunksRef.current = [];
    setRecordStatus('idle');
    setRecordedDurationMs(0);
    setVariants([]);
    setEvaluations({});
    setEvaluatingVariantId(null);
    setError(null);
    setInfo(null);
  }, [releaseRecordingResources]);

  const evaluateVariant = useCallback(
    async (variant: VoiceAudioLabVariant) => {
      if (!promptCode.trim()) {
        setError('当前没有可用 Prompt，无法发送到 Gemini Live。');
        return;
      }

      setError(null);
      setInfo(null);
      setEvaluatingVariantId(variant.id);
      try {
        const result = await evaluateVoiceAudioLab({
          audioBase64: variant.pcmBase64,
          sampleRate: variant.sampleRate,
          promptCode: promptCode.trim(),
          voiceName: (voiceName || '').trim() || undefined,
          openingAlreadyPlayed,
          variantId: variant.id,
        });
        setEvaluations((previous) => ({
          ...previous,
          [variant.id]: result,
        }));
        setInfo(`Gemini Live 已返回 ${variant.label} 的离线验证结果。`);
      } catch (evaluationError) {
        const message = evaluationError instanceof Error ? evaluationError.message : String(evaluationError);
        setError(`Gemini Live 验证失败: ${message}`);
      } finally {
        setEvaluatingVariantId(null);
      }
    },
    [openingAlreadyPlayed, promptCode, voiceName]
  );

  const summaryTag = useMemo(() => {
    if (recordStatus === 'recording') {
      return <Tag type="green">录音中 {formatDuration(recordedDurationMs)}</Tag>;
    }
    if (recordStatus === 'preparing') {
      return <Tag type="blue">处理中</Tag>;
    }
    if (hasRecording) {
      return <Tag type="teal">已生成 {variants.length} 个版本</Tag>;
    }
    return <Tag type="cool-gray">待录音</Tag>;
  }, [hasRecording, recordStatus, recordedDurationMs, variants.length]);

  return (
    <Tile className={styles.sideTile}>
      <div className={styles.diagnosticHeader}>
        <div>
          <h4 className="cds--heading-02">离线音频实验</h4>
          <p className={styles.audioCaption}>
            这块专门用于复现“同一段音频经过电话链路前后是什么样，以及直接送 Gemini Live 会返回什么”。
          </p>
        </div>
        {summaryTag}
      </div>

      <div className={styles.audioLabActionRow}>
        <Button
          kind="primary"
          size="sm"
          onClick={() => void startRecording()}
          disabled={recordStatus !== 'idle'}
        >
          开始录音
        </Button>
        <Button
          kind="secondary"
          size="sm"
          onClick={() => void stopRecording()}
          disabled={recordStatus !== 'recording' && recordStatus !== 'requesting'}
        >
          停止录音
        </Button>
        <Button
          kind="ghost"
          size="sm"
          onClick={resetLab}
          disabled={recordStatus === 'requesting' || recordStatus === 'preparing'}
        >
          清空
        </Button>
      </div>

      <Toggle
        id="voice-audio-lab-opening-toggle"
        labelA="欢迎语未播"
        labelB="欢迎语已播"
        labelText="评估时是否视为 Twilio 已经播过欢迎语"
        toggled={openingAlreadyPlayed}
        onToggle={(value) => setOpeningAlreadyPlayed(Boolean(value))}
      />

      {recordStatus === 'preparing' ? (
        <InlineLoading description="正在生成三种离线音频版本..." />
      ) : null}
      {error ? <p className={styles.audioLabError}>{error}</p> : null}
      {info ? <p className={styles.audioLabInfo}>{info}</p> : null}

      {!hasRecording && recordStatus === 'idle' ? (
        <p className={styles.emptyText}>
          先录一段用户语音。建议控制在 3-8 秒，这样最适合对比“原始录音 / 电话版 / Gemini 上送版”。
        </p>
      ) : null}

      {variants.length > 0 ? (
        <div className={styles.audioLabGrid}>
          {variants.map((variant) => {
            const evaluation = evaluations[variant.id];
            const outputText = evaluation
              ? resolveEvaluationTranscript(evaluation.outputFinal, evaluation.outputPartials) ||
                evaluation.assistantMetaTexts.join('')
              : '';
            const inputText = evaluation
              ? resolveEvaluationTranscript(evaluation.inputFinal, evaluation.inputPartials)
              : '';
            const evaluating = evaluatingVariantId === variant.id;

            return (
              <div key={variant.id} className={styles.audioDebugBlock}>
                <div className={styles.audioLabVariantHeader}>
                  <div>
                    <h5 className={styles.audioDebugHeading}>{variant.label}</h5>
                    <p className={styles.audioCaption}>{variant.description}</p>
                  </div>
                  <Tag type="cool-gray">{variant.sampleRate} Hz</Tag>
                </div>

                <audio
                  className={styles.audioPlayer}
                  controls
                  preload="metadata"
                  src={`data:audio/wav;base64,${variant.wavBase64}`}
                />

                <p className={styles.audioCaption}>
                  时长 {formatDuration(variant.durationMs)} · {formatBytes(variant.bytes)} · RMS {variant.rms} · Peak{' '}
                  {variant.peak}
                </p>

                <div className={styles.audioLabActionRow}>
                  <Button
                    kind="tertiary"
                    size="sm"
                    onClick={() => void evaluateVariant(variant)}
                    disabled={Boolean(evaluatingVariantId)}
                  >
                    发送到 Gemini
                  </Button>
                  {evaluating ? <InlineLoading description="Gemini Live 评估中..." /> : null}
                </div>

                {evaluation ? (
                  <div className={styles.audioLabResultBlock}>
                    <p className={styles.audioCaption}>
                      模型 {evaluation.model} · Prompt {evaluation.promptCode} · 上送采样率{' '}
                      {evaluation.effectiveSendSampleRate} Hz
                    </p>
                    <div className={styles.transcriptGrid}>
                      <div className={styles.transcriptCard}>
                        <h6 className={styles.transcriptHeading}>Gemini 听到的输入</h6>
                        <pre className={styles.transcriptBody}>{inputText || '暂无 input transcript'}</pre>
                      </div>
                      <div className={styles.transcriptCard}>
                        <h6 className={styles.transcriptHeading}>Gemini 的返回</h6>
                        <pre className={styles.transcriptBody}>{outputText || '暂无 output transcript'}</pre>
                      </div>
                    </div>
                    <p className={styles.audioCaption}>
                      turn_complete={String(evaluation.turnComplete)} · timed_out={String(evaluation.timedOut)} ·
                      events={evaluation.eventTypes.join(', ') || '-'}
                    </p>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </Tile>
  );
}
