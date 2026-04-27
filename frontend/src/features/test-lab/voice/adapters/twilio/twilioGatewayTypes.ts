export type DialerStatus = 'idle' | 'fetching_token' | 'registering' | 'registered' | 'error';
export type CallStatus = 'idle' | 'dialing' | 'in-call' | 'ended' | 'error';
export type GatewayLogLevel = 'info' | 'success' | 'warning' | 'error';
export type TwilioTransportMode = 'official_conversational_agents' | 'media_stream_live';
export type TwilioInboundDebugAudioKind = 'none' | 'tail' | 'followup';

export interface DialerLogItem {
  id: string;
  level: GatewayLogLevel;
  time: string;
  message: string;
}

export interface TwilioTraceEvent {
  seq: number;
  ts: number;
  type: string;
  level?: GatewayLogLevel;
  text?: string;
  final?: boolean;
}

export interface TwilioActiveTraceCall {
  callSid: string;
  lastSeq: number;
  eventCount: number;
  lastEventType: string;
  lastEventTs: number;
  lastEventText?: string;
}

export interface TwilioCapabilitySnapshot {
  configuredPhoneNumber: string;
  geminiGenerateImplemented: boolean;
  geminiLiveImplemented: boolean;
  conversationalAgentsImplemented: boolean;
  twilioWebcallImplemented: boolean;
}
