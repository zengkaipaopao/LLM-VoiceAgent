import { Tile } from '@carbon/react';

import type { EventLog } from '../../../../hooks/useLiveWebSocketConsole';
import type { DialerLogItem } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import styles from '../TwilioTabContent.module.scss';
import type { VoiceRouteMode } from './types';

interface VoiceLogsTileProps {
  routeMode: VoiceRouteMode;
  directLogs: EventLog[];
  twilioLogs: DialerLogItem[];
}

export function VoiceLogsTile({ routeMode, directLogs, twilioLogs }: VoiceLogsTileProps) {
  return (
    <Tile className={styles.logTile}>
      <h4 className="cds--heading-02">{routeMode === 'direct' ? '会话事件日志' : '拨号与链路日志'}</h4>
      {routeMode === 'direct' ? (
        directLogs.length === 0 ? (
          <p className={styles.emptyText}>暂无日志。</p>
        ) : (
          <ul className={styles.logList}>
            {directLogs.map((item) => (
              <li key={item.id} className={styles.logItem}>
                <span className={styles.logTime}>{item.time.toLocaleTimeString('zh-CN', { hour12: false })}</span>
                <span className={`${styles.logLevel} ${styles[`logLevel${item.level}`]}`}>{item.level.toUpperCase()}</span>
                <span className={styles.logMessage}>{item.message}</span>
              </li>
            ))}
          </ul>
        )
      ) : twilioLogs.length === 0 ? (
        <p className={styles.emptyText}>暂无日志。</p>
      ) : (
        <ul className={styles.logList}>
          {twilioLogs.map((item) => (
            <li key={item.id} className={styles.logItem}>
              <span className={styles.logTime}>{item.time}</span>
              <span className={`${styles.logLevel} ${styles[`logLevel${item.level}`]}`}>{item.level.toUpperCase()}</span>
              <span className={styles.logMessage}>{item.message}</span>
            </li>
          ))}
        </ul>
      )}
    </Tile>
  );
}
