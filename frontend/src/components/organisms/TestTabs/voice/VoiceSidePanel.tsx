import { useMemo } from 'react';
import { Stack, Tag, Tile } from '@carbon/react';

import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import type { PromptTemplate } from '../../../../types/shared';
import styles from '../TwilioTabContent.module.scss';
import type { DialogueHistoryItem, VoiceRouteMode } from './types';

interface VoiceSidePanelProps {
  routeMode: VoiceRouteMode;
  liveWebsocket: UseLiveWebSocketConsoleResult;
  twilioGateway: UseTwilioVoiceGatewayResult;
  selectedPromptCode: string;
  selectedPrompt?: PromptTemplate;
  effectiveVoice: string;
  isPromptVoiceConfigured: boolean;
}

function resolveTraceSpeaker(type: string): 'AI' | '用户' | '事件' {
  const normalizedType = type.toLowerCase();
  if (normalizedType === 'input_transcript') return '用户';
  if (normalizedType === 'output_transcript' || normalizedType === 'assistant_text') return 'AI';
  return '事件';
}

function resolveTraceText(type: string, text: string, isFinal?: boolean): string {
  const baseText = text.trim();
  if (!baseText) {
    return type || '-';
  }
  if ((type === 'input_transcript' || type === 'output_transcript') && isFinal === false) {
    return `${baseText} (partial)`;
  }
  return baseText;
}

function resolveTraceTime(timestampMs: number): string {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return new Date().toLocaleTimeString('zh-CN', { hour12: false });
  }
  return new Date(timestampMs).toLocaleTimeString('zh-CN', { hour12: false });
}

export function VoiceSidePanel({
  routeMode,
  liveWebsocket,
  twilioGateway,
  selectedPromptCode,
  selectedPrompt,
  effectiveVoice,
  isPromptVoiceConfigured,
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

  if (routeMode === 'direct') {
    return (
      <Stack gap={5}>
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
              <dd>{selectedPromptCode || '-'}</dd>
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
      <Tile className={styles.sideTile}>
        <h4 className="cds--heading-02">实时对话转写</h4>
        <dl className={styles.metaList}>
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
            <dd>{isPromptVoiceConfigured ? `Prompt: ${selectedPrompt?.code}` : `Resolved: ${effectiveVoice || '-'}`}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>电话链路模式</dt>
            <dd>Media Streams + Gemini Live</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>语音引擎</dt>
            <dd>Gemini Live</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>系统能力</dt>
            <dd>
              <Tag type={twilioGateway.capability.twilioWebcallImplemented ? 'green' : 'red'}>
                电话网关（Twilio）{twilioGateway.capability.twilioWebcallImplemented ? ' OK' : ' Unavailable'}
              </Tag>
              &nbsp;
              <Tag type={twilioGateway.capability.geminiLiveImplemented ? 'green' : 'red'}>
                Gemini Live {twilioGateway.capability.geminiLiveImplemented ? ' OK' : ' Unavailable'}
              </Tag>
            </dd>
          </div>
        </dl>

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
