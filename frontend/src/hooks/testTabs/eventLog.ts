export type LogLevel = 'info' | 'success' | 'warning' | 'error';

export interface EventLog {
  id: string;
  time: Date;
  level: LogLevel;
  message: string;
}

export function appendEventLog(
  previousLogs: EventLog[],
  level: LogLevel,
  message: string,
  maxEntries: number
): EventLog[] {
  const nextLogs = [
    ...previousLogs,
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      time: new Date(),
      level,
      message,
    },
  ];

  return nextLogs.slice(-maxEntries);
}
