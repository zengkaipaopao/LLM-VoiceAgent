import { useMemo } from 'react';

import { CallLog } from '../../types';

const defaultCalls: CallLog[] = [
  {
    id: 'call_1',
    direction: 'outbound',
    counterpart: '+1 415 555 0101',
    startedAt: new Date().toISOString(),
    durationSeconds: 420,
    status: 'completed',
    summary: '确认了客户需求并提交报价。',
  },
  {
    id: 'call_2',
    direction: 'inbound',
    counterpart: '+86 138 0000 0000',
    startedAt: new Date().toISOString(),
    durationSeconds: 180,
    status: 'failed',
    summary: '客户挂断，等待回拨。',
  },
];

export function useCallsStore() {
  const calls = useMemo(() => defaultCalls, []);
  return { calls };
}
