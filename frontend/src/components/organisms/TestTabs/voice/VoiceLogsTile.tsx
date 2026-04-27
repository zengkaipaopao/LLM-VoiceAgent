import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  const { t, i18n } = useTranslation(['pages']);

  return (
    <Tile className={styles.logTile}>
      <h4 className="cds--heading-02">
        {routeMode === 'direct'
          ? t('pages:test.voiceLab.logs.directTitle', 'Session event log')
          : t('pages:test.voiceLab.logs.twilioTitle', 'Dialing and bridge log')}
      </h4>
      {routeMode === 'direct' ? (
        directLogs.length === 0 ? (
          <p className={styles.emptyText}>{t('pages:test.voiceLab.logs.empty', 'No logs yet.')}</p>
        ) : (
          <ul className={styles.logList}>
            {directLogs.map((item) => (
              <li key={item.id} className={styles.logItem}>
                <span className={styles.logTime}>
                  {item.time.toLocaleTimeString(i18n.resolvedLanguage || i18n.language || undefined, {
                    hour12: false,
                  })}
                </span>
                <span className={`${styles.logLevel} ${styles[`logLevel${item.level}`]}`}>{item.level.toUpperCase()}</span>
                <span className={styles.logMessage}>{item.message}</span>
              </li>
            ))}
          </ul>
        )
      ) : twilioLogs.length === 0 ? (
        <p className={styles.emptyText}>{t('pages:test.voiceLab.logs.empty', 'No logs yet.')}</p>
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
