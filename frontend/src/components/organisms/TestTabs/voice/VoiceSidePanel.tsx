import { useMemo } from 'react';
import { Stack, Tag, Tile } from '@carbon/react';

import type { VoiceDiagnostic } from '../../../../features/test-lab/voice/diagnostics';
import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import styles from '../TwilioTabContent.module.scss';
import type { DialogueHistoryItem, VoiceRouteMode } from './types';
import { VoiceDiagnosticsTile } from './VoiceDiagnosticsTile';

interface VoiceSidePanelProps {
  routeMode: VoiceRouteMode;
  liveWebsocket: UseLiveWebSocketConsoleResult;
  twilioGateway: UseTwilioVoiceGatewayResult;
  directDiagnostic: VoiceDiagnostic | null;
  twilioDiagnostic: VoiceDiagnostic | null;
}

function resolveTraceSpeaker(type: string): 'AI' | '用户' | '事件' {
  const normalizedType = type.toLowerCase();
  if (normalizedType === 'input_transcript') return '用户';
  if (normalizedType === 'output_transcript' || normalizedType === 'assistant_text') return 'AI';
  return '事件';
}

function resolveTraceText(type: string, text: string, isFinal?: boolean): string {
  const baseText = text.trim();
  const normalizedType = type.trim();
  if (!baseText) {
    return normalizedType || '-';
  }
  if ((type === 'input_transcript' || type === 'output_transcript') && isFinal === false) {
    return `${baseText} (partial)`;
  }
  if (normalizedType !== 'input_transcript' && normalizedType !== 'output_transcript') {
    return `${normalizedType}: ${baseText}`;
  }
  return baseText;
}

function resolveTraceTime(timestampMs: number): string {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return new Date().toLocaleTimeString('zh-CN', { hour12: false });
  }
  return new Date(timestampMs).toLocaleTimeString('zh-CN', { hour12: false });
}

function findLatestTraceTurn(
  events: UseTwilioVoiceGatewayResult['traceEvents'],
  types: string[]
): string {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!types.includes(event.type)) {
      continue;
    }
    const text = resolveTraceText(event.type || '', event.text || '', event.final).trim();
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
}: VoiceSidePanelProps) {
  const directDialogueHistory = useMemo<DialogueHistoryItem[]>(() => {
    const items: DialogueHistoryItem[] = [];
    for (const log of liveWebsocket.logs) {
      const message = (log.message || '').trim();
      let role: '用户' | 'AI' | null = null;
      let text = '';

      if (message.startsWith('用户:')) {
        role = '用户';
        text = message.replace(/^用户:\s*/, '').trim();
      } else if (message.startsWith('AI:')) {
        role = 'AI';
        text = message.replace(/^AI:\s*/, '').trim();
      }

      if (!role || !text) continue;
      items.push({
        id: log.id,
        role,
        text,
        timeLabel: log.time.toLocaleTimeString('zh-CN', { hour12: false }),
        ts: log.time.getTime(),
      });
    }
    return items.slice(-240);
  }, [liveWebsocket.logs]);

  const latestUserTurn = useMemo(() => {
    for (let index = directDialogueHistory.length - 1; index >= 0; index -= 1) {
      if (directDialogueHistory[index].role === '用户') {
        return directDialogueHistory[index].text;
      }
    }
    return '';
  }, [directDialogueHistory]);

  const latestAssistantTurn = useMemo(() => {
    for (let index = directDialogueHistory.length - 1; index >= 0; index -= 1) {
      if (directDialogueHistory[index].role === 'AI') {
        return directDialogueHistory[index].text;
      }
    }
    return '';
  }, [directDialogueHistory]);

  const latestTwilioUserTurn = useMemo(
    () => findLatestTraceTurn(twilioGateway.traceEvents, ['input_transcript']),
    [twilioGateway.traceEvents]
  );

  const latestTwilioAssistantTurn = useMemo(
    () =>
      findLatestTraceTurn(twilioGateway.traceEvents, [
        'output_transcript',
        'assistant_text',
        'assistant_meta_text',
      ]),
    [twilioGateway.traceEvents]
  );

  const inboundDebugAudioTitle =
    twilioGateway.inboundDebugAudioKind === 'followup' ? '后续轮次候选音频对比' : '最近 5 秒入站音频对比';
  const inboundDebugAudioSummaryFallback =
    twilioGateway.inboundDebugAudioKind === 'followup'
      ? '已保存上一轮 AI 播放完成后检测到的第一段可疑用户语音，可直接比较 8k 原始样本与 16k 上送样本。'
      : '已保存最近 5 秒入站调试音频，可直接比较 8k 原始样本与 16k 上送样本。';
  const inboundDebugAudioLoadingText =
    twilioGateway.inboundDebugAudioKind === 'followup'
      ? '正在加载后续轮次候选双路调试音频...'
      : '正在加载最近 5 秒双路调试音频...';
  const inboundDebugAudioEmptyText =
    '通话结束或链路异常后，会自动保存最近 5 秒尾部样本；如果检测到上一轮 AI 播放完成后的疑似用户新一轮讲话，也会优先保存那段候选音频。';

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
          <h4 className="cds--heading-02">实时对话转写</h4>
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
              <dt>总 Tokens</dt>
              <dd>{liveWebsocket.totalTokens}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>当前 Prompt</dt>
              <dd>{liveWebsocket.selectedPromptCode || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>当前模型</dt>
              <dd>{liveWebsocket.model || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>预约记录</dt>
              <dd>{liveWebsocket.finalizeResult?.appointment_id || '-'}</dd>
            </div>
          </dl>
          <div className={styles.transcriptGrid}>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>用户最近一句</h5>
              <pre className={styles.transcriptBody}>{latestUserTurn || '等待用户讲话...'}</pre>
            </div>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>AI 最近一句</h5>
              <pre className={styles.transcriptBody}>{latestAssistantTurn || '等待模型回复...'}</pre>
            </div>
            <div className={styles.transcriptCard}>
              <h5 className={styles.transcriptHeading}>完整对话履历</h5>
              {directDialogueHistory.length === 0 ? (
                <p className={styles.emptyText}>暂无对话履历。</p>
              ) : (
                <ul className={styles.dialogueHistoryList}>
                  {directDialogueHistory.map((item) => (
                    <li key={`${item.id}-${item.ts}`} className={styles.dialogueHistoryItem}>
                      <span className={styles.dialogueHistoryTime}>{item.timeLabel}</span>
                      <span className={styles.dialogueHistoryRole}>{item.role}</span>
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
        <h4 className="cds--heading-02">实时对话转写</h4>
        <dl className={styles.metaList}>
          <div className={styles.metaRow}>
            <dt>浏览器外呼 Leg SID</dt>
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
            <dt>音色来源</dt>
            <dd>由 Google CX Agent Studio / CES Deployment 决定</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>电话链路模式</dt>
            <dd>Official CA + Twilio</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>语音引擎</dt>
            <dd>Conversational Agents</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>系统能力</dt>
            <dd>
              <Tag type={twilioGateway.capability.twilioWebcallImplemented ? 'green' : 'red'}>
                电话网关（Twilio）{twilioGateway.capability.twilioWebcallImplemented ? ' OK' : ' Unavailable'}
              </Tag>
              &nbsp;
              <Tag type={twilioGateway.capability.conversationalAgentsImplemented ? 'green' : 'red'}>
                {`Conversational Agents ${
                  twilioGateway.capability.conversationalAgentsImplemented ? 'OK' : 'Unavailable'
                }`}
              </Tag>
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>媒体桥状态</dt>
            <dd>
              <Tag type={twilioGateway.traceDiagnostic?.stream_active ? 'green' : 'cool-gray'}>
                {twilioGateway.traceDiagnostic?.stream_active ? 'stream_active' : 'stream_idle'}
              </Tag>
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>活跃媒体流</dt>
            <dd>{twilioGateway.activeTraceCalls.length}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>最后一条后端事件</dt>
            <dd>
              {latestTwilioTraceEvent
                ? `${latestTwilioTraceEvent.type || '-'} @ ${resolveTraceTime(latestTwilioTraceEvent.ts)}`
                : '-'}
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>转写统计</dt>
            <dd>
              用户完成 {twilioTraceStats.finalUserTurns} / AI 完成 {twilioTraceStats.finalAssistantTurns} / partial{' '}
              {twilioTraceStats.partialTurns} / 事件 {twilioTraceStats.totalEvents}
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>活跃流候选</dt>
            <dd>
              {twilioGateway.activeTraceCalls.length === 0 ? (
                '暂无活跃官方电话流。'
              ) : (
                <ul className={styles.diagnosticList}>
                  {twilioGateway.activeTraceCalls.map((item) => (
                    <li key={item.callSid} className={styles.diagnosticListItem}>
                      {item.callSid}
                      {item.lastEventType ? ` · ${item.lastEventType}` : ''}
                      {item.lastEventTs > 0 ? ` · ${resolveTraceTime(item.lastEventTs)}` : ''}
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
            <h5 className={styles.transcriptHeading}>用户最近一句</h5>
            <pre className={styles.transcriptBody}>{latestTwilioUserTurn || '等待用户讲话...'}</pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>AI 最近一句</h5>
            <pre className={styles.transcriptBody}>{latestTwilioAssistantTurn || '等待模型回复...'}</pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>{inboundDebugAudioTitle}</h5>
            {twilioGateway.inboundDebugAudioPcm8kUrl || twilioGateway.inboundDebugAudioPcm16kUrl ? (
              <>
                <div className={styles.audioDebugGroup}>
                  <div className={styles.audioDebugBlock}>
                    <h6 className={styles.audioDebugHeading}>原始 PCM8k</h6>
                    {twilioGateway.inboundDebugAudioPcm8kUrl ? (
                      <audio
                        className={styles.audioPlayer}
                        controls
                        preload="metadata"
                        src={twilioGateway.inboundDebugAudioPcm8kUrl}
                      />
                    ) : (
                      <p className={styles.emptyText}>当前通话未保存原始 PCM8k 样本。</p>
                    )}
                    <p className={styles.audioCaption}>
                      Twilio `μ-law/8kHz` 解码后的原始电话音频，不经过本地 8k→16k 升采样。
                    </p>
                  </div>
                  <div className={styles.audioDebugBlock}>
                    <h6 className={styles.audioDebugHeading}>上送前 PCM16k</h6>
                    {twilioGateway.inboundDebugAudioPcm16kUrl ? (
                      <audio
                        className={styles.audioPlayer}
                        controls
                        preload="metadata"
                        src={twilioGateway.inboundDebugAudioPcm16kUrl}
                      />
                    ) : (
                      <p className={styles.emptyText}>当前通话未保存 PCM16k 样本。</p>
                    )}
                    <p className={styles.audioCaption}>
                      后端本地升采样后、真正送给 Gemini Live 的 16k PCM 音频。
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
          <p className={styles.emptyText}>接通后会在这里显示用户/AI 转写与事件。</p>
        ) : (
          <ul className={styles.traceList}>
            {twilioGateway.traceEvents.map((event) => (
              <li key={`${event.seq}-${event.ts}`} className={styles.traceItem}>
                <span className={styles.traceTime}>{resolveTraceTime(event.ts)}</span>
                <span className={styles.traceSpeaker}>{resolveTraceSpeaker(event.type || '')}</span>
                <span className={styles.traceText}>
                  {resolveTraceText(event.type || '', event.text || '', event.final)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Tile>
    </Stack>
  );
}
