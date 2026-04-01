import { CallLog } from '../../types/shared';

export type CallFilters = Record<string, any[]>;

export type CallTableRow = {
  id: string;
  call_id: string;
  caller: string;
  status: string;
  handler: string | undefined;
  started_at: string;
  duration: number;
  confidence: number | undefined;
  raw: CallLog;
};
