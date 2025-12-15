import { useEffect, useRef, useState } from 'react';
import { Button, InlineNotification, TextInput, Tile } from '@carbon/react';
import { Call, Device } from '@twilio/voice-sdk';

import { PromptTemplate } from '../../../types';

type CallLog = {
  timestamp: string;
  message: string;
};

const DEFAULT_TWILIO_NUMBER =
  import.meta.env.VITE_TWILIO_DEFAULT_NUMBER ?? '+17753689279';

type TwilioWebCallPanelProps = {
  prompt?: PromptTemplate;
};

export function TwilioWebCallPanel({ prompt }: TwilioWebCallPanelProps) {
  const [identity, setIdentity] = useState('');
  const [dialNumber, setDialNumber] = useState('');
  const [status, setStatus] = useState<'idle' | 'ready' | 'error' | 'calling'>('idle');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<CallLog[]>([]);
  const deviceRef = useRef<Device | null>(null);
  const activeCallRef = useRef<Call | null>(null);

  const appendLog = (message: string) => {
    setLogs((prev) => [...prev, { timestamp: new Date().toLocaleTimeString(), message }]);
  };

  const initializeDevice = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/twilio/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity: identity || undefined }),
      });
      if (!response.ok) {
        throw new Error(`获取 Token 失败：${response.status}`);
      }
      const data: { identity: string; token: string } = await response.json();
      if (!identity) {
        setIdentity(data.identity);
      }

      if (deviceRef.current) {
        await deviceRef.current.unregister().catch(() => {});
        deviceRef.current.destroy();
        deviceRef.current = null;
      }

      const device = new Device(data.token, {
        logLevel: 'error',
        codecPreferences: ['opus', 'pcmu'],
      });
      device.on('registered', () => {
        appendLog('Twilio Device registered');
        setStatus('ready');
      });
      device.on('unregistered', () => appendLog('Twilio Device unregistered'));
      device.on('error', (deviceError) => {
        appendLog(`Device error: ${deviceError.message}`);
        setError(deviceError.message);
      });
      deviceRef.current = device;
      await device.register();
      if (!dialNumber.trim()) {
        setDialNumber(DEFAULT_TWILIO_NUMBER);
      }
      appendLog('Device initialized');
    } catch (err) {
      const message = err instanceof Error ? err.message : '初始化失败';
      setError(message);
      setStatus('error');
      appendLog(message);
    } finally {
      setLoading(false);
    }
  };

  const handleCall = async () => {
    if (status !== 'ready' || !deviceRef.current) {
      setError('请先初始化 Twilio Device。');
      return;
    }
    const trimmed = dialNumber.trim();
    if (!trimmed) {
      setError('请输入要拨打的号码。');
      return;
    }
    setError(null);
    setStatus('calling');
    appendLog(`Dialing ${trimmed} ...`);
    try {
      const params: Record<string, string> = { To: trimmed };
      if (prompt?.id) {
        params.PromptId = prompt.id;
      }
      const call = await deviceRef.current.connect({ params });
      activeCallRef.current = call;
      call.on('accept', () => appendLog('Call accepted'));
      call.on('disconnect', () => {
        appendLog('Call disconnected');
        setStatus('ready');
        activeCallRef.current = null;
      });
      call.on('cancel', () => {
        appendLog('Call canceled');
        setStatus('ready');
        activeCallRef.current = null;
      });
      call.on('error', (callError) => {
        appendLog(`Call error: ${callError.message}`);
        setError(callError.message);
        setStatus('ready');
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : '呼叫失败';
      appendLog(message);
      setError(message);
      setStatus('ready');
    }
  };

  const hangup = () => {
    if (activeCallRef.current) {
      activeCallRef.current.disconnect();
      activeCallRef.current = null;
      appendLog('Call disconnected by user');
      setStatus('ready');
    }
  };

  useEffect(
    () => () => {
      if (activeCallRef.current) {
        activeCallRef.current.disconnect();
      }
      if (deviceRef.current) {
        deviceRef.current.destroy();
      }
    },
    [],
  );

  return (
    <div className="twilio-panel">
      <Tile className="twilio-panel__tile">
        <h3>Twilio Web Call</h3>
        <p>使用 Twilio Voice SDK 直接从浏览器拨号，检查 webhook/ngrok 配置是否正常。</p>
        <div className="twilio-panel__form">
          <TextInput
            id="twilio-identity"
            labelText="客户端身份 Identity"
            placeholder="web-tester"
            value={identity}
            onChange={(event) => setIdentity(event.target.value)}
            disabled={status !== 'idle' && status !== 'error'}
          />
          <Button onClick={initializeDevice} disabled={loading || status === 'ready'}>
            {status === 'ready' ? '已初始化' : '初始化设备'}
          </Button>
        </div>
        <div className="twilio-panel__form">
          <TextInput
            id="twilio-dial-number"
            labelText="拨打到的号码 (E.164)"
            placeholder="+1xxxxxxxxxx"
            value={dialNumber}
            onChange={(event) => setDialNumber(event.target.value)}
            disabled={status === 'error'}
          />
          <div className="twilio-panel__buttons">
            <Button
              kind="primary"
              onClick={handleCall}
              disabled={status !== 'ready' || !dialNumber.trim()}
            >
              呼叫
            </Button>
            <Button kind="secondary" onClick={hangup} disabled={status !== 'calling'}>
              挂断
            </Button>
          </div>
        </div>
        <p>当前状态：{status === 'ready' ? '设备已就绪' : status}</p>
        {error && (
          <InlineNotification
            kind="error"
            lowContrast
            title="Twilio 错误"
            subtitle={error}
            onClose={() => setError(null)}
          />
        )}
      </Tile>
      <Tile className="twilio-panel__logs">
        <h4>调用日志</h4>
        {logs.length === 0 ? (
          <p>暂无日志。</p>
        ) : (
          <ul>
            {logs.map((log) => (
              <li key={`${log.timestamp}-${log.message}`}>
                <span className="twilio-panel__log-time">{log.timestamp}</span>
                <span>{log.message}</span>
              </li>
            ))}
          </ul>
        )}
      </Tile>
    </div>
  );
}
