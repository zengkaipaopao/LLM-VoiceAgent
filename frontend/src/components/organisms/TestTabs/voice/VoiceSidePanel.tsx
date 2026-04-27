import { useMemo } from 'react';
import { Stack, Tag, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import type { VoiceDiagnostic } from '../../../../features/test-lab/voice/diagnostics';
import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import styles from '../TwilioTabContent.module.scss';
import type { DialogueHistoryItem, VoiceRouteMode } from './types';
import { VoiceAudioLabTile } from './VoiceAudioLabTile';
import { VoiceDiagnosticsTile } from './VoiceDiagnosticsTile';

interface VoiceSidePanelProps {
  routeMode: VoiceRouteMode;
  liveWebsocket: UseLiveWebSocketConsoleResult;
  twilioGateway: UseTwilioVoiceGatewayResult;
  directDiagnostic: VoiceDiagnostic | null;
  twilioDiagnostic: VoiceDiagnostic | null;
  selectedPromptCode: string;
  effectiveVoice: string;
}

function resolveTraceSpeaker(type: string): 'assistant' | 'user' | 'event' {
  const normalizedType = type.toLowerCase();
  if (normalizedType === 'input_transcript') return 'user';
  if (normalizedType === 'output_transcript' || normalizedType === 'assistant_text') return 'assistant';
  return 'event';
}

function resolveTraceText(type: string, text: string, isFinal?: boolean, partialLabel = 'partial'): string {
  const baseText = text.trim();
  const normalizedType = type.trim();
  if (!baseText) {
    return normalizedType || '-';
  }
  if ((type === 'input_transcript' || type === 'output_transcript') && isFinal === false) {
    return `${baseText} (${partialLabel})`;
  }
  if (normalizedType !== 'input_transcript' && normalizedType !== 'output_transcript') {
    return `${normalizedType}: ${baseText}`;
  }
  return baseText;
}

function resolveTraceTime(timestampMs: number, locale?: string): string {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return new Date().toLocaleTimeString(locale || undefined, { hour12: false });
  }
  return new Date(timestampMs).toLocaleTimeString(locale || undefined, { hour12: false });
}

function findLatestTraceTurn(
  events: UseTwilioVoiceGatewayResult['traceEvents'],
  types: string[],
  partialLabel?: string
): string {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!types.includes(event.type)) {
      continue;
    }
    const text = resolveTraceText(event.type || '', event.text || '', event.final, partialLabel).trim();
    if (text) {
      return text;
    }
  }
  return '';
}

export function VoiceSidePanel({
  routeMode,
  liveWebsocket,
  twilioGateway,
  directDiagnostic,
  twilioDiagnostic,
  selectedPromptCode,
  effectiveVoice,
}: VoiceSidePanelProps) {
  const { t, i18n } = useTranslation(['pages']);
  const locale = i18n.resolvedLanguage || i18n.language || undefined;
  const isMediaStreamRoute = routeMode === 'twilio_media_stream';
  const voiceSourceLabel = isMediaStreamRoute
    ? t(
        'pages:test.voiceLab.sidePanel.voiceSourceMedia',
        'Determined by the local Prompt / Media Streams bridge configuration'
      )
    : t(
        'pages:test.voiceLab.sidePanel.voiceSourceOfficial',
        'Determined by Google CX Agent Studio / CES Deployment'
      );
  const phoneTransportLabel = isMediaStreamRoute
    ? t('pages:test.voiceLab.sidePanel.transportMedia', 'Self-hosted Media Streams + Twilio')
    : t('pages:test.voiceLab.sidePanel.transportOfficial', 'Official CA + Twilio');
  const speechEngineLabel = isMediaStreamRoute
    ? t('pages:test.voiceLab.sidePanel.engineMedia', 'Gemini Live')
    : t('pages:test.voiceLab.sidePanel.engineOfficial', 'Conversational Agents');
  const activeTraceEmptyLabel = isMediaStreamRoute
    ? t('pages:test.voiceLab.sidePanel.activeTraceEmptyMedia', 'No active self-hosted phone streams.')
    : t('pages:test.voiceLab.sidePanel.activeTraceEmptyOfficial', 'No active official phone streams.');

  const directDialogueHistory = useMemo<DialogueHistoryItem[]>(() => {
    const items: DialogueHistoryItem[] = [];
    for (const log of liveWebsocket.logs) {
      const message = (log.message || '').trim();
      let role: 'user' | 'assistant' | null = null;
      let text = '';

      if (message.startsWith('用户:')) {
        role = 'user';
        text = message.replace(/^用户:\s*/, '').trim();
      } else if (message.startsWith('AI:')) {
        role = 'assistant';
        text = message.replace(/^AI:\s*/, '').trim();
      }

      if (!role || !text) continue;
      items.push({
        id: log.id,
        role,
        text,
        timeLabel: log.time.toLocaleTimeString(locale, { hour12: false }),
        ts: log.time.getTime(),
      });
    }
    return items.slice(-240);
  }, [liveWebsocket.logs, locale]);

  const latestUserTurn = useMemo(() => {
    for (let index = directDialogueHistory.length - 1; index >= 0; index -= 1) {
      if (directDialogueHistory[index].role === 'user') {
        return directDialogueHistory[index].text;
      }
    }
    return '';
  }, [directDialogueHistory]);

  const latestAssistantTurn = useMemo(() => {
    for (let index = directDialogueHistory.length - 1; index >= 0; index -= 1) {
      if (directDialogueHistory[index].role === 'assistant') {
        return directDialogueHistory[index].text;
      }
    }
    return '';
  }, [directDialogueHistory]);

  const latestTwilioUserTurn = useMemo(
    () =>
      findLatestTraceTurn(
        twilioGateway.traceEvents,
        ['input_transcript'],
        t('pages:test.voiceLab.sidePanel.partialLabel', 'partial')
      ),
    [t, twilioGateway.traceEvents]
  );

  const latestTwilioAssistantTurn = useMemo(
    () =>
      findLatestTraceTurn(twilioGateway.traceEvents, [
        'output_transcript',
        'assistant_text',
        'assistant_meta_text',
      ], t('pages:test.voiceLab.sidePanel.partialLabel', 'partial')),
    [t, twilioGateway.traceEvents]
  );

  const inboundDebugAudioTitle =
    twilioGateway.inboundDebugAudioKind === 'followup'
      ? t('pages:test.voiceLab.sidePanel.followupAudioTitle', 'Follow-up turn candidate audio comparison')
      : t('pages:test.voiceLab.sidePanel.tailAudioTitle', 'Latest 5-second inbound audio comparison');
  const inboundDebugAudioSummaryFallback =
    twilioGateway.inboundDebugAudioKind === 'followup'
      ? t(
          'pages:test.voiceLab.sidePanel.followupAudioSummary',
          'The first suspicious user utterance detected after the previous AI playback completed has been saved, so you can compare the raw 8 kHz sample with the 16 kHz uplink sample directly.'
        )
      : t(
          'pages:test.voiceLab.sidePanel.tailAudioSummary',
          'The most recent 5 seconds of inbound debug audio have been saved, so you can compare the raw 8 kHz sample with the 16 kHz uplink sample directly.'
        );
  const inboundDebugAudioLoadingText =
    twilioGateway.inboundDebugAudioKind === 'followup'
      ? t(
          'pages:test.voiceLab.sidePanel.followupAudioLoading',
          'Loading both debug audio samples for the follow-up turn candidate...'
        )
      : t(
          'pages:test.voiceLab.sidePanel.tailAudioLoading',
          'Loading both debug audio samples for the latest 5 seconds...'
        );
  const inboundDebugAudioEmptyText =
    t(
      'pages:test.voiceLab.sidePanel.audioEmpty',
      'After the call ends or the bridge fails, the latest 5-second tail sample is saved automatically. If a suspected new user utterance is detected after the previous AI playback completes, that candidate clip is saved with higher priority.'
    );

  const twilioTraceStats = useMemo(() => {
    let finalUserTurns = 0;
    let finalAssistantTurns = 0;
    let partialTurns = 0;
    for (const event of twilioGateway.traceEvents) {
      if (event.type === 'input_transcript' && event.final !== false) {
        finalUserTurns += 1;
      } else if (event.type === 'output_transcript' && event.final !== false) {
        finalAssistantTurns += 1;
      } else if (
        (event.type === 'input_transcript' || event.type === 'output_transcript') &&
        event.final === false
      ) {
        partialTurns += 1;
      }
    }
    return {
      finalUserTurns,
      finalAssistantTurns,
      partialTurns,
      totalEvents: twilioGateway.traceEvents.length,
    };
  }, [twilioGateway.traceEvents]);

  const latestTwilioTraceEvent = useMemo(() => {
    if (twilioGateway.traceEvents.length === 0) {
      return null;
    }
    return twilioGateway.traceEvents[twilioGateway.traceEvents.length - 1];
  }, [twilioGateway.traceEvents]);

  if (routeMode === 'direct') {
    return (
      <Stack gap={5}>
        <VoiceDiagnosticsTile diagnostic={directDiagnostic} />
        <Tile className={styles.sideTile}>
          <h4 className="cds--heading-02">{t('pages:test.voiceLab.sidePanel.transcriptTitle', 'Live conversation transcript')}</h4>
          <dl className={styles.metaList}>
            <div className={styles.metaRow}>
              <dt>Session ID</dt>
              <dd>{liveWebsocket.sessionId || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>Call ID</dt>
              <dd>{liveWebsocket.testCallId || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>{t('pages:test.voiceLab.sidePanel.totalTokens', 'Total tokens')}</dt>
              <dd>{liveWebsocket.totalTokens}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>{t('pages:test.voiceLab.sidePanel.currentPrompt', 'Current Prompt')}</dt>
              <dd>{liveWebsocket.selectedPromptCode || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>{t('pages:test.voiceLab.sidePanel.currentModel', 'Current model')}</dt>
              <dd>{liveWebsocket.model || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>{t('pages:test.voiceLab.sidePanel.appointmentRecord', 'Appointment record')}</dt>
              <dd>{liveWebsocket.finalizeResult?.appointment_id || '-'}</dd>
            </div>
          </dl>
          <div className={styles.transcriptGrid}>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.sidePanel.latestUser', 'Latest user utterance')}</h5>
              <pre className={styles.transcriptBody}>
                {latestUserTurn || t('pages:test.voiceLab.sidePanel.waitingUser', 'Waiting for the user to speak...')}
              </pre>
            </div>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.sidePanel.latestAssistant', 'Latest AI utterance')}</h5>
              <pre className={styles.transcriptBody}>
                {latestAssistantTurn ||
                  t('pages:test.voiceLab.sidePanel.waitingAssistant', 'Waiting for the model to reply...')}
              </pre>
            </div>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.sidePanel.history', 'Full dialogue history')}</h5>
              {directDialogueHistory.length === 0 ? (
                <p className={styles.emptyText}>{t('pages:test.voiceLab.sidePanel.historyEmpty', 'No dialogue history yet.')}</p>
              ) : (
                <ul className={styles.dialogueHistoryList}>
                  {directDialogueHistory.map((item) => (
                    <li key={`${item.id}-${item.ts}`} className={styles.dialogueHistoryItem}>
                      <span className={styles.dialogueHistoryTime}>{item.timeLabel}</span>
                      <span className={styles.dialogueHistoryRole}>
                        {item.role === 'user'
                          ? t('pages:test.voiceLab.sidePanel.userRole', 'User')
                          : t('pages:test.voiceLab.sidePanel.assistantRole', 'AI')}
                      </span>
                      <span className={styles.dialogueHistoryText}>{item.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Tile>
      </Stack>
    );
  }

  return (
    <Stack gap={5}>
      <VoiceDiagnosticsTile
        diagnostic={twilioDiagnostic}
        loading={twilioGateway.loadingTraceDiagnostic}
      />
      <Tile className={styles.sideTile}>
        <h4 className="cds--heading-02">{t('pages:test.voiceLab.sidePanel.transcriptTitle', 'Live conversation transcript')}</h4>
        <dl className={styles.metaList}>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.browserLegSid', 'Browser outbound Leg SID')}</dt>
            <dd>{twilioGateway.sdkCallSid || '-'}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>Bound Call SID</dt>
            <dd>{twilioGateway.traceCallSid || '-'}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>Trace Cursor</dt>
            <dd>{twilioGateway.traceSeq}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.voiceSource', 'Voice source')}</dt>
            <dd>{voiceSourceLabel}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.phoneTransport', 'Phone transport mode')}</dt>
            <dd>{phoneTransportLabel}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.speechEngine', 'Speech engine')}</dt>
            <dd>{speechEngineLabel}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.capabilities', 'System capabilities')}</dt>
            <dd>
              <Tag type={twilioGateway.capability.twilioWebcallImplemented ? 'green' : 'red'}>
                {t('pages:test.voiceLab.sidePanel.twilioCapability', 'Phone gateway (Twilio)')}
                {twilioGateway.capability.twilioWebcallImplemented
                  ? t('pages:test.voiceLab.sidePanel.capabilityOk', ' OK')
                  : t('pages:test.voiceLab.sidePanel.capabilityUnavailable', ' Unavailable')}
              </Tag>
              &nbsp;
              <Tag type={twilioGateway.capability.conversationalAgentsImplemented ? 'green' : 'red'}>
                {`Conversational Agents${
                  twilioGateway.capability.conversationalAgentsImplemented
                    ? t('pages:test.voiceLab.sidePanel.capabilityOk', ' OK')
                    : t('pages:test.voiceLab.sidePanel.capabilityUnavailable', ' Unavailable')
                }`}
              </Tag>
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.bridgeStatus', 'Bridge status')}</dt>
            <dd>
              <Tag type={twilioGateway.traceDiagnostic?.stream_active ? 'green' : 'cool-gray'}>
                {twilioGateway.traceDiagnostic?.stream_active ? 'stream_active' : 'stream_idle'}
              </Tag>
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.activeStreams', 'Active streams')}</dt>
            <dd>{twilioGateway.activeTraceCalls.length}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.lastBackendEvent', 'Latest backend event')}</dt>
            <dd>
              {latestTwilioTraceEvent
                ? `${latestTwilioTraceEvent.type || '-'} @ ${resolveTraceTime(latestTwilioTraceEvent.ts, locale)}`
                : '-'}
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.transcriptStats', 'Transcript stats')}</dt>
            <dd>
              {t(
                'pages:test.voiceLab.sidePanel.transcriptStatsValue',
                'User final {{userTurns}} / AI final {{assistantTurns}} / partial {{partialTurns}} / events {{totalEvents}}',
                {
                  userTurns: twilioTraceStats.finalUserTurns,
                  assistantTurns: twilioTraceStats.finalAssistantTurns,
                  partialTurns: twilioTraceStats.partialTurns,
                  totalEvents: twilioTraceStats.totalEvents,
                }
              )}
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.voiceLab.sidePanel.activeTraceCandidates', 'Active stream candidates')}</dt>
            <dd>
              {twilioGateway.activeTraceCalls.length === 0 ? (
                activeTraceEmptyLabel
              ) : (
                <ul className={styles.diagnosticList}>
                  {twilioGateway.activeTraceCalls.map((item) => (
                    <li key={item.callSid} className={styles.diagnosticListItem}>
                      {item.callSid}
                      {item.lastEventType ? ` · ${item.lastEventType}` : ''}
                      {item.lastEventTs > 0 ? ` · ${resolveTraceTime(item.lastEventTs, locale)}` : ''}
                      {item.eventCount > 0 ? ` · events=${item.eventCount}` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </dd>
          </div>
        </dl>

        <div className={styles.transcriptGrid}>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.sidePanel.latestUser', 'Latest user utterance')}</h5>
            <pre className={styles.transcriptBody}>
              {latestTwilioUserTurn || t('pages:test.voiceLab.sidePanel.waitingUser', 'Waiting for the user to speak...')}
            </pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.sidePanel.latestAssistant', 'Latest AI utterance')}</h5>
            <pre className={styles.transcriptBody}>
              {latestTwilioAssistantTurn ||
                t('pages:test.voiceLab.sidePanel.waitingAssistant', 'Waiting for the model to reply...')}
            </pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>{inboundDebugAudioTitle}</h5>
            {twilioGateway.inboundDebugAudioPcm8kUrl || twilioGateway.inboundDebugAudioPcm16kUrl ? (
              <>
                <div className={styles.audioDebugGroup}>
                  <div className={styles.audioDebugBlock}>
                    <h6 className={styles.audioDebugHeading}>{t('pages:test.voiceLab.sidePanel.pcm8kTitle', 'Raw PCM8k')}</h6>
                    {twilioGateway.inboundDebugAudioPcm8kUrl ? (
                      <audio
                        className={styles.audioPlayer}
                        controls
                        preload="metadata"
                        src={twilioGateway.inboundDebugAudioPcm8kUrl}
                      />
                    ) : (
                      <p className={styles.emptyText}>
                        {t('pages:test.voiceLab.sidePanel.pcm8kEmpty', 'No raw PCM8k sample was saved for this call.')}
                      </p>
                    )}
                    <p className={styles.audioCaption}>
                      {t(
                        'pages:test.voiceLab.sidePanel.pcm8kDescription',
                        'The raw phone audio after Twilio `μ-law/8kHz` decode, without local 8 kHz to 16 kHz upsampling.'
                      )}
                    </p>
                  </div>
                  <div className={styles.audioDebugBlock}>
                    <h6 className={styles.audioDebugHeading}>
                      {t('pages:test.voiceLab.sidePanel.pcm16kTitle', 'PCM16k before uplink')}
                    </h6>
                    {twilioGateway.inboundDebugAudioPcm16kUrl ? (
                      <audio
                        className={styles.audioPlayer}
                        controls
                        preload="metadata"
                        src={twilioGateway.inboundDebugAudioPcm16kUrl}
                      />
                    ) : (
                      <p className={styles.emptyText}>
                        {t('pages:test.voiceLab.sidePanel.pcm16kEmpty', 'No PCM16k sample was saved for this call.')}
                      </p>
                    )}
                    <p className={styles.audioCaption}>
                      {t(
                        'pages:test.voiceLab.sidePanel.pcm16kDescription',
                        'The 16 kHz PCM audio that is actually sent to Gemini Live after backend-local upsampling.'
                      )}
                    </p>
                  </div>
                </div>
                <p className={styles.audioCaption}>
                  {twilioGateway.inboundDebugAudioSummaryText ||
                    inboundDebugAudioSummaryFallback}
                </p>
              </>
            ) : twilioGateway.loadingInboundDebugAudio ? (
              <p className={styles.emptyText}>{inboundDebugAudioLoadingText}</p>
            ) : (
              <p className={styles.emptyText}>{inboundDebugAudioEmptyText}</p>
            )}
          </div>
        </div>

        {twilioGateway.traceEvents.length === 0 ? (
          <p className={styles.emptyText}>
            {t('pages:test.voiceLab.sidePanel.traceEmpty', 'User / AI transcripts and events will appear here after the call connects.')}
          </p>
        ) : (
          <ul className={styles.traceList}>
            {twilioGateway.traceEvents.map((event) => (
              <li key={`${event.seq}-${event.ts}`} className={styles.traceItem}>
                <span className={styles.traceTime}>{resolveTraceTime(event.ts, locale)}</span>
                <span className={styles.traceSpeaker}>
                  {resolveTraceSpeaker(event.type || '') === 'user'
                    ? t('pages:test.voiceLab.sidePanel.userRole', 'User')
                    : resolveTraceSpeaker(event.type || '') === 'assistant'
                      ? t('pages:test.voiceLab.sidePanel.assistantRole', 'AI')
                      : t('pages:test.voiceLab.sidePanel.eventRole', 'Event')}
                </span>
                <span className={styles.traceText}>
                  {resolveTraceText(
                    event.type || '',
                    event.text || '',
                    event.final,
                    t('pages:test.voiceLab.sidePanel.partialLabel', 'partial')
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Tile>
      {isMediaStreamRoute ? (
        <VoiceAudioLabTile promptCode={selectedPromptCode} voiceName={effectiveVoice} />
      ) : null}
    </Stack>
  );
}
