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
          <div className={styles.diagnosticBlock}>
            <h5 className={styles.diagnosticTitle}>{diagnostic.title}</h5>
            <p className={styles.description}>{diagnostic.summary}</p>
          </div>

          <dl className={styles.metaList}>
            <div className={styles.metaRow}>
              <dt>责任面</dt>
              <dd>{diagnostic.owner || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>诊断类别</dt>
              <dd>{diagnostic.category || '-'}</dd>
            </div>
            <div className={styles.metaRow}>
              <dt>诊断来源</dt>
              <dd>{diagnostic.source}</dd>
            </div>
          </dl>

          <div className={styles.diagnosticBlock}>
            <h5 className={styles.transcriptHeading}>建议动作</h5>
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
            <h5 className={styles.transcriptHeading}>证据</h5>
            {diagnostic.evidence.length === 0 ? (
              <p className={styles.emptyText}>暂无证据项。</p>
            ) : (
              <ul className={styles.diagnosticEvidenceList}>
                {diagnostic.evidence.map((item, index) => (
                  <li key={`${diagnostic.category}-evidence-${index}`} className={styles.diagnosticEvidenceItem}>
                    <span className={styles.diagnosticEvidenceLabel}>{item.label}</span>
                    <span className={`${styles.logLevel} ${styles[`logLevel${item.level}`]}`}>{item.level.toUpperCase()}</span>
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
