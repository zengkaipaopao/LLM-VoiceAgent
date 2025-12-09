import { Tile } from '@carbon/react';

import { ConsoleLog } from './types';

type RtcLogsPanelProps = {
  logs: ConsoleLog[];
  formatTime: (timestamp: string) => string;
  sessionMeta?: { id?: string; model?: string } | null;
};

export function RtcLogsPanel({ logs, formatTime, sessionMeta }: RtcLogsPanelProps) {
  const ordered = logs.slice(-30);
  return (
    <Tile>
      <h4>事件日志</h4>
      <div className="console-log">
        {ordered.map((entry) => (
          <div key={entry.id} className={`console-log__item console-log__item--${entry.direction}`}>
            <span>{formatTime(entry.timestamp)}</span>
            <p>{entry.message}</p>
          </div>
        ))}
        {ordered.length === 0 && <p className="console-log__empty">暂无事件</p>}
      </div>
      {sessionMeta && sessionMeta.id && (
        <p className="rtc-session-tip">
          当前会话：{sessionMeta.id} · 模型：{sessionMeta.model ?? '未知'}
        </p>
      )}
    </Tile>
  );
}
