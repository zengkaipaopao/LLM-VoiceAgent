import { Button, InlineNotification, TextInput, Tile } from '@carbon/react';

import { PromptTemplate } from '../../../types';
import { useTwilioVoice } from '../hooks/useTwilioVoice';

type TwilioWebCallPanelProps = {
  prompt?: PromptTemplate;
};

export function TwilioWebCallPanel({ prompt }: TwilioWebCallPanelProps) {
  const {
    identity,
    setIdentity,
    dialNumber,
    setDialNumber,
    status,
    loading,
    error,
    logs,
    initializeDevice,
    startCall,
    hangup,
    clearError,
  } = useTwilioVoice({ promptId: prompt?.id });

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
              onClick={startCall}
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
            onClose={clearError}
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
