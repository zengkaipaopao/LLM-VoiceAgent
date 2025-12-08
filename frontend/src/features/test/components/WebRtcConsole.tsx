import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, InlineLoading, Tag, TextArea, Tile } from '@carbon/react';
import { createRealtimeSession } from '../../../api/realtime';
import { createAppointmentFromConversation } from '../../../api/appointments';
import { PromptTemplate } from '../../../types';

type RtcState = 'idle' | 'connecting' | 'connected' | 'error';

type ConsoleLog = {
  id: string;
  direction: 'in' | 'out' | 'system';
  message: string;
  timestamp: string;
};

const defaultInstructions =
  '通过 WebRTC 与来电者保持双向语音 + DataChannel，且实时使用中文解释你的推理。';
const fallbackModel = 'gpt-4o-realtime-preview-2024-12-17';

const AUTO_APPOINTMENT_PHRASES = ['ご利用ありがとうございました', 'ご用命ありがとうございました'];

const containsClosingPhrase = (text: string) =>
  AUTO_APPOINTMENT_PHRASES.some((phrase) => text.includes(phrase));

const extractRealtimeText = (payload: string): string | null => {
  try {
    const data = JSON.parse(payload);
    if (typeof data.delta === 'string') return data.delta;
    if (data.delta && typeof data.delta === 'object') {
      if (typeof data.delta.text === 'string') return data.delta.text;
      if (Array.isArray(data.delta.content)) {
        return data.delta.content
          .map((item: unknown) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object' && 'text' in item && typeof (item as { text?: string }).text === 'string') {
              return (item as { text: string }).text;
            }
            return '';
          })
          .join('');
      }
    }
    if (typeof data.text === 'string') return data.text;
  } catch {
    return payload;
  }
  return null;
};

const formatTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

type WebRtcConsoleProps = {
  prompt?: PromptTemplate;
};

export function WebRtcConsole({ prompt }: WebRtcConsoleProps) {
  const [rtcState, setRtcState] = useState<RtcState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionMeta, setSessionMeta] = useState<{ id: string; model: string } | null>(null);
  const [command, setCommand] = useState('');
  const [logs, setLogs] = useState<ConsoleLog[]>([]);
  const [savingAppointment, setSavingAppointment] = useState(false);
  const [appointmentMessage, setAppointmentMessage] = useState<string | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const hasSavedRef = useRef(false);
  const autoAppointmentTriggeredRef = useRef(false);
  const voiceConfig = prompt?.voiceConfig;
  const instructions = useMemo(() => {
    const base = prompt?.systemPrompt ?? defaultInstructions;
    const welcome = prompt?.welcomeMessage?.trim();
    const hints: string[] = [];
    if (welcome) {
      hints.push(`连接建立后先向用户播报：${welcome}`);
    }
    if (voiceConfig?.voice) {
      hints.push(`合成语音请使用 ${voiceConfig.voice} 声线。`);
    }
    if (voiceConfig?.speakingRate) {
      hints.push(`请将语速控制在 ${voiceConfig.speakingRate} 倍左右。`);
    }
    return hints.length ? `${base}\n\n[语音指引]\n${hints.join('\n')}` : base;
  }, [prompt?.systemPrompt, prompt?.welcomeMessage, voiceConfig?.speakingRate]);
  const activeModel = prompt?.modelId ?? fallbackModel;
  const activeVoice = voiceConfig?.voice;
  const noiseSuppressionEnabled = voiceConfig?.noiseSuppression ?? true;
  const appointmentEnabled = prompt?.capabilities?.appointmentLogging ?? false;

  const appendLog = useCallback((entry: Omit<ConsoleLog, 'id' | 'timestamp'>) => {
    setLogs((prev) => [
      ...prev,
      {
        ...entry,
        id: `${entry.direction}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        timestamp: new Date().toISOString(),
      },
    ]);
  }, []);

  const handleCreateAppointment = useCallback(
    async (options?: { auto?: boolean }) => {
      if (!appointmentEnabled) {
        if (!options?.auto) {
          setAppointmentMessage('当前 Prompt 未开启预约记录功能。');
        }
        return;
      }
      if (!logs.length) {
        if (!options?.auto) {
          setAppointmentMessage('暂无可用的对话记录。');
        }
        return;
      }
      if (hasSavedRef.current) {
        if (!options?.auto) {
          setAppointmentMessage('本次会话已生成预约记录。');
        }
        return;
      }
      setSavingAppointment(true);
      setAppointmentMessage(options?.auto ? '通话结束，正在生成预约记录…' : null);
      try {
        const messages = logs.map((log) => ({
          role: log.direction === 'in' ? 'assistant' : log.direction === 'out' ? 'user' : 'system',
          text: log.message,
          timestamp: log.timestamp,
        }));
        await createAppointmentFromConversation(messages);
        hasSavedRef.current = true;
        autoAppointmentTriggeredRef.current = true;
        setAppointmentMessage(
          options?.auto ? '通话结束，预约记录已自动生成。' : '预约记录已生成，可在“预约记录”页面查看。',
        );
      } catch (err) {
        console.error('创建预约记录失败', err);
        setAppointmentMessage('生成预约记录失败，请稍后再试。');
      } finally {
        setSavingAppointment(false);
      }
    },
    [appointmentEnabled, logs],
  );

  const cleanupConnection = useCallback(() => {
    dataChannelRef.current?.close();
    dataChannelRef.current = null;
    peerRef.current?.close();
    peerRef.current = null;
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
    setRtcState('idle');
  }, []);

  const setupRemoteAudio = useCallback((pc: RTCPeerConnection) => {
    const remoteStream = new MediaStream();
    pc.ontrack = (event) => {
      event.streams[0].getTracks().forEach((track) => remoteStream.addTrack(track));
      const audio = remoteAudioRef.current;
      if (audio) {
        audio.srcObject = remoteStream;
        audio.play().catch((err) => console.warn('自动播放受限', err));
      }
    };
  }, []);

  const configureDataChannel = useCallback(
    (pc: RTCPeerConnection) => {
      const channel = pc.createDataChannel('oai-events');
      dataChannelRef.current = channel;
      channel.onopen = () => {
        appendLog({ direction: 'system', message: 'DataChannel 已建立' });
        // 连接建立后立即请求模型输出，用于触发 Prompt 中配置的开场白
        const payload = JSON.stringify({ type: 'response.create' });
        channel.send(payload);
        appendLog({ direction: 'out', message: payload });
      };
      channel.onerror = (event) => appendLog({ direction: 'system', message: `DataChannel 错误: ${event}` });
      channel.onmessage = (event) => {
        appendLog({ direction: 'in', message: event.data });
        if (appointmentEnabled && !autoAppointmentTriggeredRef.current && typeof event.data === 'string') {
          const text = extractRealtimeText(event.data);
          if (text && containsClosingPhrase(text)) {
            autoAppointmentTriggeredRef.current = true;
            void handleCreateAppointment();
          }
        }
      };
    },
    [appendLog, appointmentEnabled, handleCreateAppointment],
  );

  const connectRtc = useCallback(async () => {
    if (rtcState === 'connecting' || rtcState === 'connected') return;
    setRtcState('connecting');
    setError(null);
    try {
      hasSavedRef.current = false;
      const session = await createRealtimeSession({
        instructions,
        model: activeModel,
        voice: activeVoice,
        channel: 'webrtc',
      });
      const peer = new RTCPeerConnection(session.rtc_configuration ?? undefined);
      peerRef.current = peer;
      setSessionMeta({ id: session.session_id, model: session.model });
      setupRemoteAudio(peer);
      configureDataChannel(peer);

      const audioConstraints: MediaTrackConstraints = {
        noiseSuppression: noiseSuppressionEnabled,
        echoCancellation: true,
        autoGainControl: true,
      };
      const localStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      localStreamRef.current = localStream;
      localStream.getTracks().forEach((track) => peer.addTrack(track, localStream));

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);

      const sdpResponse = await fetch(`https://api.openai.com/v1/realtime?model=${encodeURIComponent(activeModel)}`, {
        method: 'POST',
        body: offer.sdp ?? '',
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          'Content-Type': 'application/sdp',
        },
      });

      if (!sdpResponse.ok) {
        throw new Error(`OpenAI 返回错误：${await sdpResponse.text()}`);
      }
      const answer = await sdpResponse.text();
      await peer.setRemoteDescription({ type: 'answer', sdp: answer });
      setRtcState('connected');
      appendLog({ direction: 'system', message: 'WebRTC 连接已建立' });
    } catch (err) {
      console.error('建立 WebRTC 连接失败', err);
      setError(err instanceof Error ? err.message : '连接失败');
      cleanupConnection();
      setRtcState('error');
    }
  }, [
    activeModel,
    activeVoice,
    appendLog,
    cleanupConnection,
    configureDataChannel,
    instructions,
    noiseSuppressionEnabled,
    rtcState,
    setupRemoteAudio,
  ]);

  const disconnectRtc = useCallback(() => {
    cleanupConnection();
    appendLog({ direction: 'system', message: '已断开 WebRTC 连接' });
    if (appointmentEnabled) {
      void handleCreateAppointment({ auto: true });
    }
  }, [appendLog, appointmentEnabled, cleanupConnection, handleCreateAppointment]);

  const sendCommand = useCallback(() => {
    const text = command.trim();
    if (!text || !dataChannelRef.current || dataChannelRef.current.readyState !== 'open') return;
    const payload = JSON.stringify({ type: 'input_text', text });
    dataChannelRef.current.send(payload);
    appendLog({ direction: 'out', message: payload });
    setCommand('');
  }, [appendLog, command]);

  useEffect(() => {
    return () => {
      cleanupConnection();
    };
  }, [cleanupConnection]);

  const stateTag: Record<RtcState, { label: string; type: string }> = {
    idle: { label: '待准备', type: 'cool-gray' },
    connecting: { label: '连接中', type: 'blue' },
    connected: { label: '已连接', type: 'teal' },
    error: { label: '异常', type: 'red' },
  };

  const orderedLogs = useMemo(() => logs.slice(-30), [logs]);

  return (
    <div className="webrtc-console">
      <Tile className="webrtc-console__header">
        <div>
          <h3>WebRTC 音频通道</h3>
          <p>
            通过浏览器媒体轨道体验实时语音对话，可搭配 DataChannel 发送控制指令。当前模型：{activeModel} · Prompt：
            {prompt?.name ?? '默认 Prompt'}
          </p>
        </div>
        <div className="webrtc-console__actions">
          <Tag type={stateTag[rtcState].type}>{stateTag[rtcState].label}</Tag>
          <Button kind="ghost" size="sm" onClick={disconnectRtc} disabled={rtcState !== 'connected'}>
            断开
          </Button>
          <Button kind="primary" size="sm" onClick={connectRtc} disabled={rtcState === 'connecting'}>
            {rtcState === 'connected' ? '重新连接' : '建立连接'}
          </Button>
        </div>
      </Tile>
      <Tile>
        <div className="rtc-audio-preview">
          <div>
            <h4>远端 Audio 输出</h4>
            <p>允许浏览器播放声音即可听到机器人语音。</p>
          </div>
          <audio ref={remoteAudioRef} controls autoPlay className="rtc-audio-element" />
        </div>
        <div className="rtc-data-channel">
          <h4>DataChannel 控制</h4>
          <p>向模型发送 JSON 指令，例如 `input_text` / `response.create`。</p>
          <div className="rtc-command-row">
            <TextArea
              id="rtc-command-input"
              labelText="指令载荷"
              value={command}
              rows={4}
              onChange={(event) => setCommand(event.target.value)}
              placeholder='{ "type": "input_text", "text": "请重复上一句" }'
              disabled={rtcState !== 'connected'}
            />
            <Button type="button" onClick={sendCommand} disabled={!command.trim() || rtcState !== 'connected'}>
              发送指令
            </Button>
          </div>
        </div>
        {error && (
          <div className="rtc-error">
            <InlineLoading status="error" description={error} />
          </div>
        )}
      </Tile>
      <Tile>
        <h4>事件日志</h4>
        <div className="console-log">
          {orderedLogs.map((entry) => (
            <div key={entry.id} className={`console-log__item console-log__item--${entry.direction}`}>
              <span>{formatTime(entry.timestamp)}</span>
              <p>{entry.message}</p>
            </div>
          ))}
          {orderedLogs.length === 0 && <p className="console-log__empty">暂无事件</p>}
        </div>
        {sessionMeta && (
          <p className="rtc-session-tip">
            当前会话：{sessionMeta.id} · 模型：{sessionMeta.model}
          </p>
        )}
      </Tile>
      {appointmentEnabled && (
        <Tile className="session-panel">
          <div>
            <h4>预约记录</h4>
            <p className="session-panel__helper">将当前日志发送给后端，由模型自动提取预约信息并存档。</p>
            {appointmentMessage && <p className="session-panel__helper">{appointmentMessage}</p>}
          </div>
          <Button
            kind="primary"
            size="sm"
            disabled={savingAppointment || !logs.length}
            onClick={() => {
              void handleCreateAppointment();
            }}
          >
            {savingAppointment ? '生成中...' : '生成预约记录'}
          </Button>
        </Tile>
      )}
    </div>
  );
}
