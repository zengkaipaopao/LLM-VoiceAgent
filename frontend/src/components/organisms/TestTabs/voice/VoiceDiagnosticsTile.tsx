import { Stack, Tag, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import type { VoiceDiagnostic } from '../../../../features/test-lab/voice/diagnostics';
import styles from '../TwilioTabContent.module.scss';

interface VoiceDiagnosticsTileProps {
  diagnostic: VoiceDiagnostic | null;
  loading?: boolean;
}

function toTagType(status: VoiceDiagnostic['status']): 'green' | 'red' | 'blue' | 'cool-gray' {
  if (status === 'ok') return 'green';
  if (status === 'error') return 'red';
  if (status === 'warning') return 'blue';
  return 'cool-gray';
}

function toStatusLabel(status: VoiceDiagnostic['status'], t: (key: string, defaultValue?: string) => string): string {
  if (status === 'ok') return t('pages:test.voiceLab.diagnostics.status.ok', 'OK');
  if (status === 'error') return t('pages:test.voiceLab.diagnostics.status.error', 'Error');
  if (status === 'warning') return t('pages:test.voiceLab.diagnostics.status.warning', 'Warning');
  return t('pages:test.voiceLab.diagnostics.status.unknown', 'Unknown');
}

function toMetaTagType(status: VoiceDiagnostic['status']): 'green' | 'red' | 'blue' | 'cool-gray' {
  return toTagType(status);
}

function formatDiagnosticOwner(owner: string): string {
  const mapping: Record<string, string> = {
    system: '系统',
    backend: '后端配置',
    backend_bridge: '后端桥接',
    backend_or_model: '后端 / 模型',
    backend_audio_pipeline: '后端音频链路',
    browser_device: '浏览器设备',
    browser_network: '浏览器网络',
    client_activity_boundaries: '本地活动边界',
    duplex_audio_path: '双工音频链路',
    gemini_live_turn_detection: 'Gemini Live 回合检测',
    gemini_or_prompt: 'Gemini / Prompt',
    google_cloud_auth: 'Google Cloud 认证',
    google_cloud_iam: 'Google Cloud IAM',
    model_configuration: '模型配置',
    prompt_or_model_config: 'Prompt / 模型配置',
    twilio: 'Twilio',
    twilio_credentials: 'Twilio 凭证',
    twilio_transport: 'Twilio 传输层',
    unknown: '未判定',
  };
  return mapping[owner] || owner.replace(/_/g, ' ');
}

function formatDiagnosticCategory(category: string): string {
  const mapping: Record<string, string> = {
    healthy: '链路正常',
    assistant_audio_empty: '模型音频为空',
    assistant_audio_not_playing: '模型音频未播放',
    assistant_not_responding: '模型未响应',
    backend_configuration: '后端配置错误',
    duplex_overlap_vad_conflict: '双工重叠干扰 VAD',
    gemini_turn_detection_stalled: 'Gemini 未提交新回合',
    google_adc_missing: 'ADC 凭证缺失',
    google_vertex_permission: 'Vertex 权限不足',
    manual_activity_end_missing: '手动结束边界缺失',
    media_stream_bridge_runtime: '媒体桥运行时故障',
    no_trace_events: '暂无 Trace',
    twilio_call_status: 'Twilio 呼叫状态错误',
    twilio_media_stream_transport: 'Twilio 媒体流传输错误',
    twilio_stream_unexpected_stop: '媒体流提前停止',
    upstream_audio_without_turn: '上行有语音但未形成回合',
    user_heard_no_reply: '用户发言后无回复',
  };
  return mapping[category] || category.replace(/_/g, ' ');
}

function formatDiagnosticSource(source: VoiceDiagnostic['source']): string {
  const mapping: Record<VoiceDiagnostic['source'], string> = {
    backend_trace: '后端 Trace',
    frontend_direct: '浏览器直连',
    frontend_gateway: '前端网关',
  };
  return mapping[source] || source;
}

function formatEvidenceLabel(label: string): string {
  const mapping: Record<string, string> = {
    audio_stream_end_sent: '上行收口',
    audio_stream_resumed: '上行恢复',
    duplex_overlap_detected: '双工重叠',
    gemini_turn_detection_stalled: '回合未提交',
    manual_activity_end_overdue: '结束边界超时',
    manual_activity_end_sent: '结束边界发出',
    manual_activity_progress: '活动窗口进度',
    manual_activity_silence_reset: '静音累计被打断',
    manual_activity_start_sent: '开始边界发出',
    media_stream_status: '媒体流状态',
    playback_clear_sent: '清理播放缓冲',
    playback_complete: '播放完成',
    playback_mark_sent: '播放标记',
    stream_error: '流错误',
    stream_stop: '流结束',
  };
  return mapping[label] || label.replace(/_/g, ' ');
}

export function VoiceDiagnosticsTile({ diagnostic, loading = false }: VoiceDiagnosticsTileProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.sideTile}>
      <div className={styles.diagnosticHeader}>
        <h4 className="cds--heading-02">{t('pages:test.voiceLab.diagnostics.title', 'Bridge diagnostics')}</h4>
        <Tag type={toTagType(diagnostic?.status || 'unknown')}>
          {diagnostic
            ? toStatusLabel(diagnostic.status, (key, defaultValue) => t(key, defaultValue || ''))
            : loading
              ? t('pages:test.voiceLab.diagnostics.loadingShort', 'Loading')
              : t('pages:test.voiceLab.diagnostics.status.unknown', 'Unknown')}
        </Tag>
      </div>

      {!diagnostic ? (
        <p className={styles.emptyText}>
          {loading
            ? t('pages:test.voiceLab.diagnostics.loading', 'Generating diagnostics for the current route...')
            : t(
                'pages:test.voiceLab.diagnostics.empty',
                'No diagnostics are available yet. After the call connects or fails, this section will show ownership, evidence, and next actions.'
              )}
        </p>
      ) : (
        <Stack gap={4}>
          <div className={styles.diagnosticHero}>
            <div className={styles.diagnosticHeroTags}>
              <Tag type={toMetaTagType(diagnostic.status)}>{formatDiagnosticOwner(diagnostic.owner || 'unknown')}</Tag>
              <Tag type="cool-gray">{formatDiagnosticCategory(diagnostic.category || '-')}</Tag>
              <Tag type="cool-gray">{formatDiagnosticSource(diagnostic.source)}</Tag>
            </div>
            <div className={styles.diagnosticBlock}>
              <p className={styles.diagnosticEyebrow}>{t('pages:test.voiceLab.diagnostics.currentAssessment', 'Current assessment')}</p>
              <h5 className={styles.diagnosticTitle}>{diagnostic.title}</h5>
              <p className={styles.description}>{diagnostic.summary}</p>
            </div>
          </div>

          <div className={styles.diagnosticBlock}>
            <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.diagnostics.suggestedActions', 'Suggested next actions')}</h5>
            {diagnostic.actions.length === 0 ? (
              <p className={styles.emptyText}>{t('pages:test.voiceLab.diagnostics.actionsEmpty', 'No suggested actions yet.')}</p>
            ) : (
              <ul className={styles.diagnosticList}>
                {diagnostic.actions.map((item, index) => (
                  <li key={`${diagnostic.category}-action-${index}`} className={styles.diagnosticListItem}>
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={styles.diagnosticBlock}>
            <div className={styles.diagnosticSectionHeader}>
              <h5 className={styles.transcriptHeading}>{t('pages:test.voiceLab.diagnostics.evidenceTitle', 'Key evidence')}</h5>
              <span className={styles.diagnosticHint}>
                {t('pages:test.voiceLab.diagnostics.evidenceCount', 'Latest {{count}} items', {
                  count: diagnostic.evidence.length,
                })}
              </span>
            </div>
            {diagnostic.evidence.length === 0 ? (
              <p className={styles.emptyText}>{t('pages:test.voiceLab.diagnostics.evidenceEmpty', 'No evidence items yet.')}</p>
            ) : (
              <ul className={styles.diagnosticEvidenceList}>
                {diagnostic.evidence.map((item, index) => (
                  <li key={`${diagnostic.category}-evidence-${index}`} className={styles.diagnosticEvidenceItem}>
                    <div className={styles.diagnosticEvidenceMeta}>
                      <span className={styles.diagnosticEvidenceLabel}>{formatEvidenceLabel(item.label)}</span>
                      <span className={`${styles.logLevel} ${styles[`logLevel${item.level}`]}`}>
                        {item.level.toUpperCase()}
                      </span>
                    </div>
                    <span className={styles.logMessage}>{item.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Stack>
      )}
    </Tile>
  );
}
