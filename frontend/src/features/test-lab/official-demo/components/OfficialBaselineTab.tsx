import { useEffect, useMemo } from 'react';
import { Button, InlineLoading, Stack, Tag, TextInput, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import {
  TestTabNotifications,
  TestWorkbenchShell,
  type TestWorkbenchSummaryItem,
} from '../../../../components/molecules/TestTabs';
import { VoiceDiagnosticsTile } from '../../../../components/organisms/TestTabs/voice/VoiceDiagnosticsTile';
import { VoiceLogsTile } from '../../../../components/organisms/TestTabs/voice/VoiceLogsTile';
import styles from '../../../../components/organisms/TestTabs/TwilioTabContent.module.scss';
import { useTwilioVoiceGateway } from '../../voice/adapters/twilio/useTwilioVoiceGateway';
import {
  classifyGatewayFallbackDiagnostic,
  mapBackendTraceDiagnostic,
} from '../../voice/diagnostics';

const DEFAULT_IDENTITY = 'webcall-tester';
const OFFICIAL_CA_TRANSPORT_LABEL = '官方 Conversational Agents 基线（Google CX Agent Studio + Twilio）';

function toDialerTone(
  status: 'idle' | 'fetching_token' | 'registering' | 'registered' | 'error'
): TestWorkbenchSummaryItem['tone'] {
  if (status === 'registered') return 'green';
  if (status === 'fetching_token' || status === 'registering') return 'blue';
  if (status === 'error') return 'red';
  return 'cool-gray';
}

function toCallTone(
  status: 'idle' | 'dialing' | 'in-call' | 'ended' | 'error'
): TestWorkbenchSummaryItem['tone'] {
  if (status === 'in-call') return 'green';
  if (status === 'dialing') return 'blue';
  if (status === 'error') return 'red';
  return 'cool-gray';
}

function resolveTraceSpeaker(type: string): 'AI' | '用户' | '事件' {
  const normalizedType = type.toLowerCase();
  if (normalizedType === 'input_transcript') return '用户';
  if (
    normalizedType === 'output_transcript' ||
    normalizedType === 'assistant_text' ||
    normalizedType === 'assistant_meta_text'
  ) {
    return 'AI';
  }
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
  if (
    normalizedType !== 'input_transcript' &&
    normalizedType !== 'output_transcript' &&
    normalizedType !== 'assistant_text'
  ) {
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
  events: Array<{ type: string; text?: string; final?: boolean }>,
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

export function OfficialBaselineTab() {
  const { t } = useTranslation(['pages']);
  const twilioGateway = useTwilioVoiceGateway({
    identity: DEFAULT_IDENTITY,
    transportMode: 'official_conversational_agents',
    requirePrompt: false,
    transportLabel: OFFICIAL_CA_TRANSPORT_LABEL,
  });

  useEffect(() => {
    void twilioGateway.refreshCapability();
  }, [twilioGateway.refreshCapability]);

  const configLocked =
    twilioGateway.callStatus === 'dialing' || twilioGateway.callStatus === 'in-call';
  const canDial =
    twilioGateway.dialerStatus === 'registered' &&
    (twilioGateway.callStatus === 'idle' || twilioGateway.callStatus === 'ended');
  const canHangup =
    twilioGateway.callStatus === 'dialing' || twilioGateway.callStatus === 'in-call';

  const diagnostic = useMemo(
    () =>
      mapBackendTraceDiagnostic(twilioGateway.traceDiagnostic) ||
      classifyGatewayFallbackDiagnostic({
        error: twilioGateway.error,
        dialerStatus: twilioGateway.dialerStatus,
        callStatus: twilioGateway.callStatus,
        logs: twilioGateway.logs,
        traceEvents: twilioGateway.traceEvents,
      }),
    [
      twilioGateway.callStatus,
      twilioGateway.dialerStatus,
      twilioGateway.error,
      twilioGateway.logs,
      twilioGateway.traceDiagnostic,
      twilioGateway.traceEvents,
    ]
  );

  const latestTraceEvent = useMemo(() => {
    if (twilioGateway.traceEvents.length === 0) {
      return null;
    }
    return twilioGateway.traceEvents[twilioGateway.traceEvents.length - 1];
  }, [twilioGateway.traceEvents]);

  const latestUserTurn = useMemo(
    () => findLatestTraceTurn(twilioGateway.traceEvents, ['input_transcript']),
    [twilioGateway.traceEvents]
  );
  const latestAssistantTurn = useMemo(
    () =>
      findLatestTraceTurn(twilioGateway.traceEvents, [
        'output_transcript',
        'assistant_text',
        'assistant_meta_text',
      ]),
    [twilioGateway.traceEvents]
  );

  const traceStats = useMemo(() => {
    let finalUserTurns = 0;
    let finalAssistantTurns = 0;
    let partialTurns = 0;
    for (const event of twilioGateway.traceEvents) {
      if (event.type === 'input_transcript' && event.final !== false) {
        finalUserTurns += 1;
      } else if (
        (event.type === 'output_transcript' || event.type === 'assistant_text') &&
        event.final !== false
      ) {
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

  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'goal',
      label: '测试目标',
      value: '官方 CA 电话链路',
      tone: 'teal',
    },
    {
      id: 'route',
      label: '接入方式',
      value: 'CX Agent Studio + Twilio',
      tone: 'teal',
    },
    {
      id: 'connection',
      label: '连接状态',
      value: twilioGateway.callStatus,
      tone: toCallTone(twilioGateway.callStatus),
      mono: true,
    },
    {
      id: 'audio',
      label: '音频采集',
      value: twilioGateway.dialerStatus,
      tone: toDialerTone(twilioGateway.dialerStatus),
      mono: true,
    },
    {
      id: 'routeLabel',
      label: '路由',
      value: twilioGateway.transportMode,
      mono: true,
      tone: 'cool-gray',
    },
  ];

  const warning =
    '这个标签严格走 Google Conversational Agents / CX Agent Studio 官方电话适配链路，不读取业务 Prompt，也不覆盖 Gemini Live 音色。';

  const main = (
    <Stack gap={5}>
      <Tile className={styles.mainTile}>
        <section className={styles.sectionBlock}>
          <div className={styles.headerRow}>
            <div className={styles.sectionHeader}>
              <h4 className="cds--heading-03">官方 CA 配置</h4>
              <p className={styles.description}>
                这条链路不再走 `Gemini Live` 直连桥，而是按 Google 官方 `Conversational Agents / CX Agent
                Studio` 电话适配思路，通过 Twilio Media Streams 接到 Google `SessionService /
                BidiRunSession`。
              </p>
            </div>
            {twilioGateway.loadingCapability ? (
              <InlineLoading description="加载配置中..." />
            ) : (
              <Button
                kind="ghost"
                size="sm"
                disabled={configLocked}
                onClick={() => {
                  void twilioGateway.refreshCapability();
                }}
              >
                刷新配置
              </Button>
            )}
          </div>

          {configLocked ? (
            <p className={styles.description}>会话进行中，配置已锁定。请先断开当前会话后再修改配置。</p>
          ) : null}

          <div className={styles.formGrid}>
            <TextInput
              id="official-ca-transport"
              labelText="当前接入方式"
              value={OFFICIAL_CA_TRANSPORT_LABEL}
              readOnly
              helperText="后端固定走 official_conversational_agents 路由，不再复用当前业务 Gemini Live 基线路径。"
            />

            <TextInput
              id="official-ca-agent-runtime"
              labelText="后端运行时"
              value="Google SessionService / BidiRunSession"
              readOnly
              helperText="Agent / Deployment / Voice 均由 Google Conversational Agents 部署侧决定，不在此页面覆盖。"
            />

            <TextInput
              id="official-ca-identity"
              labelText="Client Identity"
              value={DEFAULT_IDENTITY}
              readOnly
            />

            <TextInput
              id="official-ca-target-number"
              labelText="目标号码（E.164）"
              value={twilioGateway.targetNumber}
              onChange={(event) => twilioGateway.setTargetNumber(event.target.value)}
              readOnly={twilioGateway.targetNumberLocked || configLocked}
              helperText={
                twilioGateway.targetNumberLocked
                  ? '已锁定为后端 TWILIO_PHONE_NUMBER。浏览器外呼会先拨到这个 Twilio 号码。'
                  : '请输入可拨打号码，例如 +8150xxxxxxx。'
              }
            />

            <TextInput
              id="official-ca-inbound-number"
              labelText="已配置入站号码（Twilio）"
              value={twilioGateway.capability.configuredPhoneNumber || '-'}
              readOnly
              helperText="真实手机直接拨打这个号码，也会走 official_conversational_agents 这条官方 CA 链路。"
            />
          </div>
        </section>

        <section className={styles.sectionBlock}>
          <h4 className="cds--heading-03">连接控制</h4>
          <p className={styles.description}>
            这条链路只验证官方电话适配基线。你可以先“准备下一通入呼”后用真实手机拨打，也可以走 Token →
            设备注册 → 浏览器外呼，二者都会进入同一条官方 CA 电话链路。
          </p>

          <div className={styles.actionRow}>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.prepareInboundCall({})}
              disabled={configLocked}
            >
              准备下一通入呼
            </Button>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.fetchToken()}
              disabled={configLocked}
            >
              获取 Token
            </Button>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.registerDevice()}
              disabled={configLocked}
            >
              初始化设备
            </Button>
            <Button
              kind="primary"
              size="sm"
              onClick={() => void twilioGateway.startDial({})}
              disabled={!canDial}
            >
              开始语音对话
            </Button>
            <Button
              kind="danger--tertiary"
              size="sm"
              onClick={twilioGateway.hangupCall}
              disabled={!canHangup}
            >
              挂断
            </Button>
            <Button
              kind="ghost"
              size="sm"
              onClick={twilioGateway.unregisterDevice}
              disabled={configLocked}
            >
              注销设备
            </Button>
          </div>
        </section>
      </Tile>

      <VoiceLogsTile routeMode="twilio" directLogs={[]} twilioLogs={twilioGateway.logs} />
    </Stack>
  );

  const side = (
    <Stack gap={5}>
      <VoiceDiagnosticsTile
        diagnostic={diagnostic}
        loading={twilioGateway.loadingTraceDiagnostic}
      />
      <Tile className={styles.sideTile}>
        <h4 className="cds--heading-02">官方 CA Trace</h4>
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
            <dt>路由模式</dt>
            <dd>{twilioGateway.transportMode}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>系统能力</dt>
            <dd>
              <Tag type={twilioGateway.capability.twilioWebcallImplemented ? 'green' : 'red'}>
                电话网关（Twilio）{twilioGateway.capability.twilioWebcallImplemented ? ' OK' : ' Unavailable'}
              </Tag>
              &nbsp;
              <Tag
                type={
                  twilioGateway.capability.conversationalAgentsImplemented ? 'green' : 'red'
                }
              >
                CX Agent Studio{' '}
                {twilioGateway.capability.conversationalAgentsImplemented ? ' OK' : ' Unavailable'}
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
              {latestTraceEvent
                ? `${latestTraceEvent.type || '-'} @ ${resolveTraceTime(latestTraceEvent.ts)}`
                : '-'}
            </dd>
          </div>
          <div className={styles.metaRow}>
            <dt>转写统计</dt>
            <dd>
              用户完成 {traceStats.finalUserTurns} / AI 完成 {traceStats.finalAssistantTurns} / partial{' '}
              {traceStats.partialTurns} / 事件 {traceStats.totalEvents}
            </dd>
          </div>
        </dl>

        <div className={styles.transcriptGrid}>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>用户最近一句</h5>
            <pre className={styles.transcriptBody}>{latestUserTurn || '等待用户讲话...'}</pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>AI 最近一句</h5>
            <pre className={styles.transcriptBody}>{latestAssistantTurn || '等待代理回复...'}</pre>
          </div>
          <div className={styles.transcriptCard}>
            <h5 className={styles.transcriptHeading}>最近 5 秒入站音频对比</h5>
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
                  </div>
                </div>
                <p className={styles.audioCaption}>
                  {twilioGateway.inboundDebugAudioSummaryText ||
                    '用于确认官方 CA 链路中，Twilio 原始电话音频与上送到 Google 的 16k 音频是否保持清晰可懂。'}
                </p>
              </>
            ) : twilioGateway.loadingInboundDebugAudio ? (
              <p className={styles.emptyText}>正在加载最近 5 秒双路调试音频...</p>
            ) : (
              <p className={styles.emptyText}>通话结束后会在这里提供 8k / 16k 两路回放样本。</p>
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

  return (
    <Stack gap={5}>
      <TestTabNotifications
        error={twilioGateway.error}
        info={twilioGateway.info}
        warning={warning}
        errorTitle={t('pages:test.voiceLab.notifications.errorTitle', '请求失败')}
        successTitle={t('pages:test.voiceLab.notifications.successTitle', '执行成功')}
        warningTitle={t('pages:test.voiceLab.notifications.warningTitle', '配置提示')}
        onClearError={() => twilioGateway.setError(null)}
        onClearInfo={() => twilioGateway.setInfo(null)}
      />

      <TestWorkbenchShell
        title="官方 Conversational Agents 电话 Demo"
        description="按 Google CX Agent Studio / Conversational Agents 官方电话适配思路搭建的最小基线，用来和当前业务 Gemini Live 电话桥做严格隔离对照。"
        summaryItems={summaryItems}
        main={main}
        side={side}
      />
    </Stack>
  );
}
