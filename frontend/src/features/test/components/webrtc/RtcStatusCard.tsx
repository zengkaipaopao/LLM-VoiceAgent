import { Button, Tag, Tile } from '@carbon/react';

import { RtcState, RtcStateTag } from './types';

type RtcStatusCardProps = {
  stateTag: RtcStateTag;
  promptName?: string;
  modelName: string;
  sessionId?: string;
  rtcState: RtcState;
  error?: string | null;
  logCount: number;
  onConnect: () => void;
  onDisconnect: () => void;
  onClearLogs: () => void;
};

export function RtcStatusCard({
  stateTag,
  promptName,
  modelName,
  sessionId,
  rtcState,
  error,
  logCount,
  onConnect,
  onDisconnect,
  onClearLogs,
}: RtcStatusCardProps) {
  const isConnecting = rtcState === 'connecting';
  const isConnected = rtcState === 'connected';

  return (
    <Tile className="ws-status-card">
      <div className="ws-status-card__info">
        <Tag type={stateTag.type} size="sm">
          {stateTag.label}
        </Tag>
        <div>
          <h4>{promptName ?? '默认 Prompt'}</h4>
          <p>
            模型：{modelName} · Session：{sessionId ?? '尚未建立'}
          </p>
        </div>
      </div>
      <div className="ws-status-card__actions">
        <Button kind="primary" size="sm" onClick={onConnect} disabled={isConnecting || isConnected}>
          建立连接
        </Button>
        <Button kind="ghost" size="sm" onClick={onDisconnect} disabled={!isConnected && !isConnecting}>
          断开
        </Button>
        <Button kind="ghost" size="sm" onClick={onClearLogs} disabled={logCount === 0}>
          清空日志
        </Button>
        {error && <span className="ws-status-card__error">{error}</span>}
      </div>
    </Tile>
  );
}
