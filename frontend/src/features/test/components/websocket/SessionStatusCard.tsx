import { Button, Tag, Tile } from '@carbon/react';

import { ConnectionState, ConnectionSummary, RealtimeSessionMeta } from './types';

type SessionStatusCardProps = {
  connectionSummary: ConnectionSummary;
  promptName?: string;
  displayModel: string;
  sessionMeta: RealtimeSessionMeta;
  connectionState: ConnectionState;
  sessionError: string | null;
  messageCount: number;
  onConnect: () => void;
  onDisconnect: () => void;
  onClear: () => void;
};

export function SessionStatusCard({
  connectionSummary,
  promptName,
  displayModel,
  sessionMeta,
  connectionState,
  sessionError,
  messageCount,
  onConnect,
  onDisconnect,
  onClear,
}: SessionStatusCardProps) {
  const isConnecting = connectionState === 'connecting';
  const isConnected = connectionState === 'connected';

  return (
    <Tile className="ws-status-card">
      <div className="ws-status-card__info">
        <Tag type={connectionSummary.type} size="sm">
          {connectionSummary.label}
        </Tag>
        <div>
          <h4>{promptName ?? '默认 Prompt'}</h4>
          <p>
            模型：{displayModel} · Session：{sessionMeta?.id ?? '尚未建立'}
          </p>
        </div>
      </div>
      <div className="ws-status-card__actions">
        <Button kind="primary" size="sm" onClick={onConnect} disabled={isConnecting || isConnected}>
          建立连接
        </Button>
        <Button
          kind="ghost"
          size="sm"
          onClick={onDisconnect}
          disabled={!isConnected && !isConnecting}
        >
          断开
        </Button>
        <Button kind="ghost" size="sm" onClick={onClear} disabled={messageCount === 0}>
          清空对话
        </Button>
        {sessionError && <span className="ws-status-card__error">{sessionError}</span>}
      </div>
    </Tile>
  );
}
