import { useTranslation } from 'react-i18next';

import { EventLog } from '../../../../hooks/useTwilioWebCallConsole';
import styles from '../TwilioTabContent.module.scss';

interface TwilioLogPanelProps {
  logs: EventLog[];
}

export function TwilioLogPanel({ logs }: TwilioLogPanelProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.logPanel}>
      <h4 className="cds--heading-01">{t('pages:test.twilio.logs.title', '事件日志')}</h4>
      {logs.length === 0 ? (
        <p className={styles.emptyLog}>
          {t('pages:test.twilio.logs.empty', '暂无日志，执行一次初始化或拨号后会显示事件。')}
        </p>
      ) : (
        <ul className={styles.logList}>
          {logs.map((log) => (
            <li key={log.id} className={styles.logItem}>
              <span className={styles.logTime}>
                {log.time.toLocaleTimeString('ja-JP', { hour12: false })}
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
  );
}
