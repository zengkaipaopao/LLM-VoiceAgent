import { FormEvent, useMemo, useState } from 'react';
import { Button, InlineNotification, TextArea, TextInput, Tile } from '@carbon/react';
import { createRealtimeSession } from '../../../api/realtime';
import { PromptTemplate } from '../../../types';

type SipState = 'idle' | 'provisioning' | 'ready' | 'error';

const defaultInstructions =
  'Handle SIP callers with a steady, professional tone and tailor the script based on SIP header routing cues.';
const fallbackModel = 'gpt-4o-realtime-preview-2024-12-17';

type SipConsoleProps = {
  prompt?: PromptTemplate;
};

export function SipConsole({ prompt }: SipConsoleProps) {
  const [sipUri, setSipUri] = useState('sip:agent@pbx.example.com');
  const [fromNumber, setFromNumber] = useState('+12025550111');
  const [headers, setHeaders] = useState(`{
  "X-Workflow": "voice-debug"
}`);
  const [status, setStatus] = useState<SipState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<{ id: string; client_secret: string; model: string } | null>(null);
  const instructions = useMemo(
    () => prompt?.instructions || prompt?.systemPrompt || defaultInstructions,
    [prompt?.instructions, prompt?.systemPrompt],
  );
  const activeModel = prompt?.modelId ?? fallbackModel;
  const activeVoice = prompt?.voiceConfig?.voice;

  const handleProvision = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus('provisioning');
    setError(null);
    try {
      const parsedHeaders = headers.trim() ? JSON.parse(headers) : undefined;
      const session = await createRealtimeSession({
        instructions,
        model: activeModel,
        voice: activeVoice,
        channel: 'sip',
        sip: {
          to: sipUri,
          from: fromNumber,
          headers: parsedHeaders,
        },
      });
      setSessionInfo({ id: session.session_id, client_secret: session.client_secret, model: session.model });
      setStatus('ready');
    } catch (err) {
      console.error('SIP 会话创建失败', err);
      setError(err instanceof Error ? err.message : 'SIP 会话创建失败');
      setStatus('error');
    }
  };

  return (
    <div className="sip-console">
      <Tile>
        <h3>SIP 桥接</h3>
        <p>
          将 Realtime 模型映射到 PBX / 呼叫中心的 SIP Trunk。配置后的 `client_secret` 可在服务端注入，<br />
          由语音网关发起 INVITE 即可让机器人接管通话。当前模型：{activeModel} · Prompt：{prompt?.name ?? '默认 Prompt'}
        </p>
      </Tile>
      <Tile>
        <form className="sip-form" onSubmit={handleProvision}>
          <TextInput
            id="sip-uri"
            labelText="目标 SIP URI"
            value={sipUri}
            onChange={(event) => setSipUri(event.target.value)}
            required
          />
          <TextInput
            id="sip-from"
            labelText="主叫号码 / From"
            value={fromNumber}
            onChange={(event) => setFromNumber(event.target.value)}
            required
          />
          <TextArea
            id="sip-headers"
            labelText="自定义 SIP Headers (JSON)"
            rows={6}
            value={headers}
            onChange={(event) => setHeaders(event.target.value)}
          />
          <Button type="submit" disabled={status === 'provisioning'}>
            {status === 'provisioning' ? '创建中...' : '创建 SIP 会话'}
          </Button>
        </form>
        {error && (
          <InlineNotification
            kind="error"
            title="创建失败"
            subtitle={error}
            lowContrast
            hideCloseButton
          />
        )}
      </Tile>
      <Tile>
        <h4>联调指引</h4>
        <ol className="sip-steps">
          <li>在 PBX 或 SBC 中配置新的外线，指向上方 SIP URI。</li>
          <li>从语音入口发起 INVITE，将 `client_secret` 携带在鉴权或自定义 Header 中。</li>
          <li>由后端根据 `session_id` 选择要绑定的模型或提示词 preset。</li>
          <li>通话中可继续调用 `/realtime/session` 传入新的 SIP 参数实现转接。</li>
        </ol>
        {sessionInfo && (
          <div className="sip-session">
            <p>当前 Session ID：{sessionInfo.id}</p>
            <p>Client Secret：{sessionInfo.client_secret}</p>
            <p>模型：{sessionInfo.model}</p>
            <p>Prompt：{prompt?.name ?? '默认 Prompt'}</p>
          </div>
        )}
      </Tile>
    </div>
  );
}
