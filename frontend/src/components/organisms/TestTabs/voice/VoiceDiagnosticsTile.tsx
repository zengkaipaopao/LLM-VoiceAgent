import { Stack, Tag, Tile } from '@carbon/react';

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

function toStatusLabel(status: VoiceDiagnostic['status']): string {
  if (status === 'ok') return '正常';
  if (status === 'error') return '错误';
  if (status === 'warning') return '警告';
  return '未知';
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
  return (
    <Tile className={styles.sideTile}>
      <div className={styles.diagnosticHeader}>
        <h4 className="cds--heading-02">链路诊断</h4>
        <Tag type={toTagType(diagnostic?.status || 'unknown')}>
          {diagnostic ? toStatusLabel(diagnostic.status) : loading ? '加载中' : '未判定'}
        </Tag>
      </div>

      {!diagnostic ? (
        <p className={styles.emptyText}>
          {loading ? '正在生成当前链路诊断...' : '当前还没有可用诊断。接通或报错后，这里会显示责任面、证据和处理建议。'}
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
              <p className={styles.diagnosticEyebrow}>当前判断</p>
              <h5 className={styles.diagnosticTitle}>{diagnostic.title}</h5>
              <p className={styles.description}>{diagnostic.summary}</p>
            </div>
          </div>

          <div className={styles.diagnosticBlock}>
            <h5 className={styles.transcriptHeading}>建议先做</h5>
            {diagnostic.actions.length === 0 ? (
              <p className={styles.emptyText}>暂无建议动作。</p>
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
              <h5 className={styles.transcriptHeading}>关键证据</h5>
              <span className={styles.diagnosticHint}>最近 {diagnostic.evidence.length} 条</span>
            </div>
            {diagnostic.evidence.length === 0 ? (
              <p className={styles.emptyText}>暂无证据项。</p>
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
