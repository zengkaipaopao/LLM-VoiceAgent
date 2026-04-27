import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, InlineLoading, Tag, Tile, Toggle } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation(['pages']);
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

  const describeVariant = useCallback(
    (variant: VoiceAudioLabVariant) => {
      if (variant.id === 'original_recording') {
        return {
          label: t('pages:test.voiceLab.audioLab.variants.original.label', 'Original recording'),
          description: t(
            'pages:test.voiceLab.audioLab.variants.original.description',
            'The raw mono PCM recording captured in the browser, without phone-path degradation.'
          ),
        };
      }
      if (variant.id === 'twilio_preview') {
        return {
          label: t('pages:test.voiceLab.audioLab.variants.twilio.label', 'Twilio phone preview'),
          description: t(
            'pages:test.voiceLab.audioLab.variants.twilio.description',
            'Simulates how 16 kHz PCM sounds after entering the phone path, being downsampled to 8 kHz and encoded/decoded through μ-law.'
          ),
        };
      }
      if (variant.id === 'gemini_preview') {
        return {
          label: t('pages:test.voiceLab.audioLab.variants.gemini.label', 'Gemini uplink preview'),
          description: t(
            'pages:test.voiceLab.audioLab.variants.gemini.description',
            'Simulates the version actually sent to Gemini Live after μ-law decode, input gating, and 8 kHz to 16 kHz upsampling on phone ingress.'
          ),
        };
      }
      return {
        label: variant.label,
        description: variant.description,
      };
    },
    [t]
  );

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
      setError(t('pages:test.voiceLab.audioLab.errors.emptyRecording', 'The recording is empty. Record another sample and try again.'));
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
      setInfo(
        t(
          'pages:test.voiceLab.audioLab.info.variantsPrepared',
          'Three offline audio variants have been generated. You can replay them individually and send them to Gemini Live for validation.'
        )
      );
    } catch (prepareError) {
      const message = prepareError instanceof Error ? prepareError.message : String(prepareError);
      setError(
        t('pages:test.voiceLab.audioLab.errors.prepareFailed', 'Failed to prepare offline audio variants: {{message}}', {
          message,
        })
      );
      setVariants([]);
    } finally {
      setRecordStatus('idle');
    }
  }, [recordStatus, releaseRecordingResources, t]);

  const startRecording = useCallback(async () => {
    if (recordStatus !== 'idle') {
      return;
    }

    const AudioContextCtor = getAudioContextCtor();
    if (!AudioContextCtor) {
      setError(t('pages:test.voiceLab.audioLab.errors.webAudioUnsupported', 'This browser does not support the Web Audio API.'));
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
      setError(
        t('pages:test.voiceLab.audioLab.errors.recordStartFailed', 'Failed to start recording: {{message}}', {
          message,
        })
      );
      setRecordStatus('idle');
    }
  }, [recordStatus, releaseRecordingResources, t]);

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
        setError(
          t(
            'pages:test.voiceLab.audioLab.errors.promptMissing',
            'There is no available Prompt, so the clip cannot be sent to Gemini Live.'
          )
        );
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
        setInfo(
          t(
            'pages:test.voiceLab.audioLab.info.evaluationReady',
            'Gemini Live has returned the offline validation result for {{variant}}.',
            { variant: describeVariant(variant).label }
          )
        );
      } catch (evaluationError) {
        const message = evaluationError instanceof Error ? evaluationError.message : String(evaluationError);
        setError(
          t('pages:test.voiceLab.audioLab.errors.evaluationFailed', 'Gemini Live validation failed: {{message}}', {
            message,
          })
        );
      } finally {
        setEvaluatingVariantId(null);
      }
    },
    [describeVariant, openingAlreadyPlayed, promptCode, t, voiceName]
  );

  const summaryTag = useMemo(() => {
    if (recordStatus === 'recording') {
      return (
        <Tag type="green">
          {t('pages:test.voiceLab.audioLab.summary.recording', 'Recording')} {formatDuration(recordedDurationMs)}
        </Tag>
      );
    }
    if (recordStatus === 'preparing') {
      return <Tag type="blue">{t('pages:test.voiceLab.audioLab.summary.preparing', 'Preparing')}</Tag>;
    }
    if (hasRecording) {
      return (
        <Tag type="teal">
          {t('pages:test.voiceLab.audioLab.summary.ready', 'Prepared {{count}} variants', {
            count: variants.length,
          })}
        </Tag>
      );
    }
    return <Tag type="cool-gray">{t('pages:test.voiceLab.audioLab.summary.idle', 'Ready to record')}</Tag>;
  }, [hasRecording, recordStatus, recordedDurationMs, t, variants.length]);

  return (
    <Tile className={styles.sideTile}>
      <div className={styles.diagnosticHeader}>
        <div>
          <h4 className="cds--heading-02">{t('pages:test.voiceLab.audioLab.title', 'Offline audio lab')}</h4>
          <p className={styles.audioCaption}>
            {t(
              'pages:test.voiceLab.audioLab.description',
              'Use this section to reproduce how the same clip sounds before and after the phone path, and what Gemini Live returns when each version is sent directly.'
            )}
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
          {t('pages:test.voiceLab.audioLab.actions.startRecording', 'Start recording')}
        </Button>
        <Button
          kind="secondary"
          size="sm"
          onClick={() => void stopRecording()}
          disabled={recordStatus !== 'recording' && recordStatus !== 'requesting'}
        >
          {t('pages:test.voiceLab.audioLab.actions.stopRecording', 'Stop recording')}
        </Button>
        <Button
          kind="ghost"
          size="sm"
          onClick={resetLab}
          disabled={recordStatus === 'requesting' || recordStatus === 'preparing'}
        >
          {t('pages:test.voiceLab.audioLab.actions.clear', 'Clear')}
        </Button>
      </div>

      <Toggle
        id="voice-audio-lab-opening-toggle"
        labelA={t('pages:test.voiceLab.audioLab.toggle.openingNotPlayed', 'Opening not played')}
        labelB={t('pages:test.voiceLab.audioLab.toggle.openingPlayed', 'Opening already played')}
        labelText={t(
          'pages:test.voiceLab.audioLab.toggle.label',
          'Whether to evaluate this as if Twilio has already played the opening message'
        )}
        toggled={openingAlreadyPlayed}
        onToggle={(value) => setOpeningAlreadyPlayed(Boolean(value))}
      />

      {recordStatus === 'preparing' ? (
        <InlineLoading
          description={t(
            'pages:test.voiceLab.audioLab.loading.prepare',
            'Preparing the three offline audio variants...'
          )}
        />
      ) : null}
      {error ? <p className={styles.audioLabError}>{error}</p> : null}
      {info ? <p className={styles.audioLabInfo}>{info}</p> : null}

      {!hasRecording && recordStatus === 'idle' ? (
        <p className={styles.emptyText}>
          {t(
            'pages:test.voiceLab.audioLab.empty',
            'Record a user utterance first. A 3-8 second clip is best for comparing the original recording, the phone preview, and the Gemini uplink preview.'
          )}
        </p>
      ) : null}

      {variants.length > 0 ? (
        <div className={styles.audioLabGrid}>
          {variants.map((variant) => {
            const variantCopy = describeVariant(variant);
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
                    <h5 className={styles.audioDebugHeading}>{variantCopy.label}</h5>
                    <p className={styles.audioCaption}>{variantCopy.description}</p>
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
                  {t(
                    'pages:test.voiceLab.audioLab.metrics',
                    'Duration {{duration}} · {{bytes}} · RMS {{rms}} · Peak {{peak}}',
                    {
                      duration: formatDuration(variant.durationMs),
                      bytes: formatBytes(variant.bytes),
                      rms: variant.rms,
                      peak: variant.peak,
                    }
                  )}
                </p>

                <div className={styles.audioLabActionRow}>
                  <Button
                    kind="tertiary"
                    size="sm"
                    onClick={() => void evaluateVariant(variant)}
                    disabled={Boolean(evaluatingVariantId)}
                  >
                    {t('pages:test.voiceLab.audioLab.actions.sendToGemini', 'Send to Gemini')}
                  </Button>
                  {evaluating ? (
                    <InlineLoading
                      description={t('pages:test.voiceLab.audioLab.loading.evaluate', 'Evaluating with Gemini Live...')}
                    />
                  ) : null}
                </div>

                {evaluation ? (
                  <div className={styles.audioLabResultBlock}>
                    <p className={styles.audioCaption}>
                      {t(
                        'pages:test.voiceLab.audioLab.evaluation.meta',
                        'Model {{model}} · Prompt {{prompt}} · Send sample rate {{sampleRate}} Hz',
                        {
                          model: evaluation.model,
                          prompt: evaluation.promptCode,
                          sampleRate: evaluation.effectiveSendSampleRate,
                        }
                      )}
                    </p>
                    <div className={styles.transcriptGrid}>
                      <div className={styles.transcriptCard}>
                        <h6 className={styles.transcriptHeading}>
                          {t('pages:test.voiceLab.audioLab.evaluation.inputTitle', 'Gemini heard')}
                        </h6>
                        <pre className={styles.transcriptBody}>
                          {inputText || t('pages:test.voiceLab.audioLab.evaluation.inputEmpty', 'No input transcript')}
                        </pre>
                      </div>
                      <div className={styles.transcriptCard}>
                        <h6 className={styles.transcriptHeading}>
                          {t('pages:test.voiceLab.audioLab.evaluation.outputTitle', 'Gemini response')}
                        </h6>
                        <pre className={styles.transcriptBody}>
                          {outputText || t('pages:test.voiceLab.audioLab.evaluation.outputEmpty', 'No output transcript')}
                        </pre>
                      </div>
                    </div>
                    <p className={styles.audioCaption}>
                      {t(
                        'pages:test.voiceLab.audioLab.evaluation.flags',
                        'turn_complete={{turnComplete}} · timed_out={{timedOut}} · events={{events}}',
                        {
                          turnComplete: String(evaluation.turnComplete),
                          timedOut: String(evaluation.timedOut),
                          events: evaluation.eventTypes.join(', ') || '-',
                        }
                      )}
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
