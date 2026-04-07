import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, InlineLoading, Stack, Tag, Tile } from '@carbon/react';

import { http } from '../../../api/http';
import { TestTabNotifications, TestWorkbenchShell, type TestWorkbenchSummaryItem } from '../../molecules/TestTabs';
import styles from './TwilioTabContent.module.scss';

type ModuleStatus = 'planned' | 'in_progress' | 'implemented' | 'blocked';

interface DevModule {
  id: string;
  phase: string;
  title: string;
  description: string;
  status: ModuleStatus;
  source: 'capability_matrix' | 'rebuild_plan';
}

const MODULE_STATUS_LABEL: Record<ModuleStatus, string> = {
  planned: '计划中',
  in_progress: '进行中',
  implemented: '已完成',
  blocked: '阻塞',
};

const MODULE_STATUS_TONE: Record<ModuleStatus, 'green' | 'blue' | 'warm-gray' | 'red'> = {
  planned: 'warm-gray',
  in_progress: 'blue',
  implemented: 'green',
  blocked: 'red',
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function readCapabilityStatus(matrix: Record<string, unknown>, key: string): string {
  const node = asRecord(matrix[key]);
  const status = node.status;
  return typeof status === 'string' ? status.trim().toLowerCase() : '';
}

function normalizeCapabilityStatus(rawStatus: string, fallback: ModuleStatus): ModuleStatus {
  if (!rawStatus) return fallback;
  if (rawStatus === 'implemented') return 'implemented';
  if (rawStatus === 'in_progress') return 'in_progress';
  if (rawStatus === 'planned') return 'planned';
  if (rawStatus === 'disabled') return 'blocked';
  if (rawStatus.includes('not_implemented')) return 'planned';
  return fallback;
}

export function TwilioTabContent() {
  const { t } = useTranslation(['pages']);
  const [capabilityMatrix, setCapabilityMatrix] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  const loadCapabilityMatrix = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await http.get('/health/capabilities');
      const payload = asRecord(response.data).data;
      setCapabilityMatrix(asRecord(payload));
      setLastUpdatedAt(new Date().toISOString());
      setInfo(t('pages:test.twilio.rebuild.refreshed', '模块状态已刷新。'));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : String(loadError);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadCapabilityMatrix();
  }, [loadCapabilityMatrix]);

  const twilioWebcallStatus = normalizeCapabilityStatus(
    readCapabilityStatus(capabilityMatrix, 'twilio_webcall'),
    'planned'
  );
  const inboundEngineStatus = normalizeCapabilityStatus(
    readCapabilityStatus(capabilityMatrix, 'twilio_inbound_voice_engine'),
    'planned'
  );
  const geminiGatewayStatus = normalizeCapabilityStatus(
    readCapabilityStatus(capabilityMatrix, 'gemini_live_gateway'),
    'planned'
  );

  const modules = useMemo<DevModule[]>(
    () => [
      {
        id: 'twilio-entry',
        phase: 'M1',
        title: t('pages:test.twilio.rebuild.modules.entry.title', 'Twilio 入站接入'),
        description: t(
          'pages:test.twilio.rebuild.modules.entry.description',
          '处理已购号码入站 webhook，并建立通话会话上下文。'
        ),
        status: twilioWebcallStatus,
        source: 'capability_matrix',
      },
      {
        id: 'media-bridge',
        phase: 'M2',
        title: t('pages:test.twilio.rebuild.modules.bridge.title', '媒体流桥接层'),
        description: t(
          'pages:test.twilio.rebuild.modules.bridge.description',
          '将 Twilio 音频流转发到统一语音引擎适配层，并保持稳定生命周期控制。'
        ),
        status: inboundEngineStatus,
        source: 'capability_matrix',
      },
      {
        id: 'gemini-runtime',
        phase: 'M3',
        title: t('pages:test.twilio.rebuild.modules.gemini.title', 'Gemini Live 运行时'),
        description: t(
          'pages:test.twilio.rebuild.modules.gemini.description',
          '通过 Gemini Live 会话驱动回合控制、回复生成与语音输出。'
        ),
        status: geminiGatewayStatus,
        source: 'capability_matrix',
      },
      {
        id: 'prompt-routing',
        phase: 'M4',
        title: t('pages:test.twilio.rebuild.modules.prompt.title', 'Prompt 路由与会话策略'),
        description: t(
          'pages:test.twilio.rebuild.modules.prompt.description',
          '在统一解析器中绑定 Prompt 模板、音色配置与通话级覆盖参数。'
        ),
        status: 'in_progress',
        source: 'rebuild_plan',
      },
      {
        id: 'trace-observability',
        phase: 'M5',
        title: t('pages:test.twilio.rebuild.modules.trace.title', '实时追踪与诊断'),
        description: t(
          'pages:test.twilio.rebuild.modules.trace.description',
          '采集用户/AI 回合与关键事件，支持可复现的回归排障。'
        ),
        status: 'in_progress',
        source: 'rebuild_plan',
      },
      {
        id: 'domain-persistence',
        phase: 'M6',
        title: t('pages:test.twilio.rebuild.modules.persistence.title', '业务落库与结果固化'),
        description: t(
          'pages:test.twilio.rebuild.modules.persistence.description',
          '按明确数据契约落库最终通话结果与预约提取结果。'
        ),
        status: 'planned',
        source: 'rebuild_plan',
      },
    ],
    [geminiGatewayStatus, inboundEngineStatus, t, twilioWebcallStatus]
  );

  const implementedCount = modules.filter((module) => module.status === 'implemented').length;
  const inProgressCount = modules.filter((module) => module.status === 'in_progress').length;
  const blockedCount = modules.filter((module) => module.status === 'blocked').length;
  const completion = modules.length > 0 ? Math.round((implementedCount / modules.length) * 100) : 0;

  const inboundEngine = asRecord(capabilityMatrix.twilio_inbound_voice_engine);
  const twilioWebcall = asRecord(capabilityMatrix.twilio_webcall);
  const configuredPhoneNumber = String(twilioWebcall.configured_phone_number ?? '-');
  const defaultEngine = String(inboundEngine.default_engine ?? '-');
  const activityMode = String(inboundEngine.gemini_activity_mode ?? '-');
  const supportedEngines = Array.isArray(inboundEngine.supported_engines)
    ? inboundEngine.supported_engines.filter((engine): engine is string => typeof engine === 'string').join(', ')
    : '-';

  const summaryItems: TestWorkbenchSummaryItem[] = [
    {
      id: 'scenario',
      label: t('pages:test.twilio.rebuild.summary.scenario', '场景'),
      value: t('pages:test.twilio.rebuild.summary.scenarioValue', 'Twilio 入站功能重构'),
    },
    {
      id: 'progress',
      label: t('pages:test.twilio.rebuild.summary.progress', '进度'),
      value: `${implementedCount}/${modules.length} · ${completion}%`,
      tone: completion >= 100 ? 'green' : completion > 0 ? 'blue' : 'warm-gray',
    },
    {
      id: 'inProgress',
      label: t('pages:test.twilio.rebuild.summary.inProgress', '进行中'),
      value: String(inProgressCount),
      tone: inProgressCount > 0 ? 'blue' : 'cool-gray',
    },
    {
      id: 'blocked',
      label: t('pages:test.twilio.rebuild.summary.blocked', '阻塞'),
      value: String(blockedCount),
      tone: blockedCount > 0 ? 'red' : 'cool-gray',
    },
    {
      id: 'engine',
      label: t('pages:test.twilio.rebuild.summary.engine', '默认引擎'),
      value: defaultEngine,
      mono: true,
      tone: 'teal',
    },
  ];

  return (
    <TestWorkbenchShell
      title={t('pages:test.twilio.rebuild.shell.title', 'Twilio 重构工作台')}
      description={t(
        'pages:test.twilio.rebuild.shell.description',
        '已清空旧版 Twilio 调试控件。当前页面仅保留模块状态看板，用于分阶段重建入站 AI 流程。'
      )}
      summaryItems={summaryItems}
      notice={
        <TestTabNotifications
          error={error}
          info={info}
          errorTitle={t('pages:test.twilio.rebuild.notice.errorTitle', '请求失败')}
          successTitle={t('pages:test.twilio.rebuild.notice.successTitle', '状态已更新')}
          onClearError={() => setError(null)}
          onClearInfo={() => setInfo(null)}
        />
      }
      main={
        <Stack gap={5}>
          <Tile className={styles.headerTile}>
            <div className={styles.headerRow}>
              <div>
                <h4 className="cds--heading-03">
                  {t('pages:test.twilio.rebuild.main.title', 'Twilio 模块开发看板')}
                </h4>
                <p className={styles.description}>
                  {t(
                    'pages:test.twilio.rebuild.main.description',
                    '旧版拨号与注入调试已移除。请按模块顺序开发，状态稳定后再推进下一阶段。'
                  )}
                </p>
              </div>
              <Button
                kind="secondary"
                size="sm"
                onClick={() => void loadCapabilityMatrix()}
                disabled={loading}
              >
                {t('pages:test.twilio.rebuild.main.refresh', '刷新状态')}
              </Button>
            </div>
            <div className={styles.loadingRow}>
              {loading ? (
                <InlineLoading description={t('pages:test.twilio.rebuild.main.loading', '正在加载能力矩阵...')} />
              ) : (
                <span className={styles.timestamp}>
                  {t('pages:test.twilio.rebuild.main.lastUpdated', '最近更新')}:&nbsp;
                  {lastUpdatedAt ? new Date(lastUpdatedAt).toLocaleString() : '-'}
                </span>
              )}
            </div>
          </Tile>

          <Tile className={styles.modulesTile}>
            <div className={styles.moduleGrid}>
              {modules.map((module) => (
                <article key={module.id} className={styles.moduleCard}>
                  <div className={styles.cardHeader}>
                    <span className={styles.phaseLabel}>{module.phase}</span>
                    <Tag type={MODULE_STATUS_TONE[module.status]}>{MODULE_STATUS_LABEL[module.status]}</Tag>
                  </div>
                  <h5 className="cds--heading-01">{module.title}</h5>
                  <p className={styles.moduleDescription}>{module.description}</p>
                  <p className={styles.sourceLabel}>
                    {t('pages:test.twilio.rebuild.modules.source', '状态来源')}:&nbsp;
                    {module.source === 'capability_matrix'
                      ? t('pages:test.twilio.rebuild.modules.sourceCapability', '后端 /health/capabilities')
                      : t('pages:test.twilio.rebuild.modules.sourcePlan', '人工重构计划')}
                  </p>
                </article>
              ))}
            </div>
          </Tile>
        </Stack>
      }
      side={
        <Stack gap={5}>
          <Tile className={styles.sideTile}>
            <h4 className="cds--heading-02">
              {t('pages:test.twilio.rebuild.side.snapshotTitle', '能力快照')}
            </h4>
            <dl className={styles.metaList}>
              <div className={styles.metaRow}>
                <dt>{t('pages:test.twilio.rebuild.side.phone', '入站号码配置')}</dt>
                <dd>{configuredPhoneNumber || '-'}</dd>
              </div>
              <div className={styles.metaRow}>
                <dt>{t('pages:test.twilio.rebuild.side.engine', '默认语音引擎')}</dt>
                <dd>{defaultEngine || '-'}</dd>
              </div>
              <div className={styles.metaRow}>
                <dt>{t('pages:test.twilio.rebuild.side.supported', '支持引擎')}</dt>
                <dd>{supportedEngines || '-'}</dd>
              </div>
              <div className={styles.metaRow}>
                <dt>{t('pages:test.twilio.rebuild.side.activityMode', 'Gemini 活动模式')}</dt>
                <dd>{activityMode || '-'}</dd>
              </div>
            </dl>
          </Tile>

          <Tile className={styles.sideTile}>
            <h4 className="cds--heading-02">
              {t('pages:test.twilio.rebuild.side.sequenceTitle', '推荐开发顺序')}
            </h4>
            <ol className={styles.sequenceList}>
              <li>{t('pages:test.twilio.rebuild.side.sequence1', '先稳定 M1-M3 传输与运行时链路。')}</li>
              <li>{t('pages:test.twilio.rebuild.side.sequence2', '再实现确定性的 Prompt 路由策略（M4）。')}</li>
              <li>{t('pages:test.twilio.rebuild.side.sequence3', '完成追踪与落库契约（M5-M6）。')}</li>
              <li>{t('pages:test.twilio.rebuild.side.sequence4', '通过电话回归后，再按需恢复高级调试控件。')}</li>
            </ol>
          </Tile>
        </Stack>
      }
    />
  );
}
