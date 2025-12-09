export type RtcState = 'idle' | 'connecting' | 'connected' | 'error';

export type ConsoleLog = {
  id: string;
  direction: 'in' | 'out' | 'system';
  message: string;
  timestamp: string;
};

export type RtcStateTag = {
  label: string;
  type: string;
};
