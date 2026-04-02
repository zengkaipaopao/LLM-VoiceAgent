import { TextArea, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { EventLog } from '../../../../hooks/useLiveWebSocketConsole';
import styles from '../WebSocketTabContent.module.scss';

interface WebSocketSidePanelsProps {
  inputTranscript: string;
  outputTranscript: string;
  assistantText: string;
  logs: EventLog[];
}

export function WebSocketSidePanels({
  inputTranscript,
  outputTranscript,
  assistantText,
  logs,
}: WebSocketSidePanelsProps) {
  const { t, i18n } = useTranslation(['pages']);

  return (
    <>
      <Tile className={styles.panelTile}>
        <h4 className="cds--heading-01">
          {t('pages:test.websocket.sections.transcript', 'Realtime Transcripts')}
        </h4>
        <TextArea
          id="input-transcript"
          labelText={t('pages:test.websocket.sections.inputTranscript', 'Input Transcript')}
          rows={4}
          readOnly
          value={inputTranscript}
        />
        <TextArea
          id="output-transcript"
          labelText={t('pages:test.websocket.sections.outputTranscript', 'Output Transcript')}
          rows={4}
          readOnly
          value={outputTranscript}
        />
        <TextArea
          id="assistant-text"
          labelText={t('pages:test.websocket.sections.textOutput', 'Model Text Output')}
          rows={6}
          readOnly
          value={assistantText}
        />
      </Tile>

      <Tile className={styles.panelTile}>
        <h4 className="cds--heading-01">
          {t('pages:test.websocket.sections.logs', 'Event Logs')}
        </h4>
        <div className={styles.logPanel}>
          {logs.length === 0 ? (
            <p className={styles.emptyLog}>
              {t('pages:test.websocket.logs.empty', 'No logs yet. Connect and start a turn.')}
            </p>
          ) : (
            <ul className={styles.logList}>
              {logs.map((log) => (
                <li key={log.id} className={styles.logItem}>
                  <span className={styles.logTime}>
                    {log.time.toLocaleTimeString(i18n.language || undefined, { hour12: false })}
                  </span>
                  <span className={`${styles.logLevel} ${styles[`logLevel${log.level}`]}`}>
                    {log.level.toUpperCase()}
                  </span>
                  <span className={styles.logMessage}>{log.message}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Tile>
    </>
  );
}
