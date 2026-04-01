import { LogLevel } from '../testTabs/eventLog';
import { LiveEventPayload, SocketStatus } from './types';

interface HandleLiveEventOptions {
  event: LiveEventPayload;
  setSocketStatus: (value: SocketStatus) => void;
  startHeartbeat: () => void;
  pushLog: (level: LogLevel, message: string) => void;
  setSessionId: (value: string) => void;
  appendAssistantText: (value: string) => void;
  setInputTranscript: (value: string) => void;
  setOutputTranscript: (value: string) => void;
  playPcmAudioChunk: (chunk: string, mimeType?: string) => Promise<void>;
  setTotalTokens: (value: number) => void;
  setError: (value: string) => void;
}

export async function handleLiveEventPayload({
  event,
  setSocketStatus,
  startHeartbeat,
  pushLog,
  setSessionId,
  appendAssistantText,
  setInputTranscript,
  setOutputTranscript,
  playPcmAudioChunk,
  setTotalTokens,
  setError,
}: HandleLiveEventOptions): Promise<void> {
  switch ((event.type || '').toLowerCase()) {
    case 'connected':
      setSocketStatus('connected');
      startHeartbeat();
      pushLog('success', 'Live gateway connected.');
      return;
    case 'session_ready':
      if (event.session_id) {
        setSessionId(event.session_id);
        pushLog('success', `Gemini Live session ready: ${event.session_id}`);
      }
      return;
    case 'text':
      if (event.text) {
        appendAssistantText(event.text);
      }
      return;
    case 'input_transcript':
      if (typeof event.text === 'string') {
        setInputTranscript(event.text);
      }
      return;
    case 'output_transcript':
      if (typeof event.text === 'string') {
        setOutputTranscript(event.text);
      }
      return;
    case 'audio_chunk':
      if (event.data) {
        await playPcmAudioChunk(event.data, event.mime_type);
      }
      return;
    case 'usage':
      if (typeof event.total_tokens === 'number') {
        setTotalTokens(event.total_tokens);
      }
      return;
    case 'turn_complete':
      appendAssistantText('\n');
      if (event.reason) {
        pushLog('info', `Turn complete: ${event.reason}`);
      } else {
        pushLog('info', 'Turn complete.');
      }
      return;
    case 'interrupted':
      pushLog('warning', 'Model response interrupted by activity.');
      return;
    case 'warning':
      pushLog('warning', event.message || 'Live warning');
      return;
    case 'error':
      setError(event.error || 'Live websocket error');
      setSocketStatus('error');
      pushLog('error', event.error || 'Live websocket error');
      return;
    default:
      return;
  }
}
