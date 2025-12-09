import { Tile, Toggle } from '@carbon/react';

import { ConnectionSummary, RealtimeSessionMeta, SessionStats } from './types';

type SessionInfoPanelProps = {
  sessionMeta: RealtimeSessionMeta;
  connectionSummary: ConnectionSummary;
  stats: SessionStats;
  formatTime: (timestamp?: string | number) => string;
  autoReply: boolean;
  onToggleAutoReply: () => void;
};

export function SessionInfoPanel({
  sessionMeta,
  connectionSummary,
  stats,
  formatTime,
  autoReply,
  onToggleAutoReply,
}: SessionInfoPanelProps) {
  return (
    <Tile className="session-panel">
      <div>
        <h3>会话状态</h3>
        <p className="session-panel__helper">在这里查看实时连接与轮次情况，可随时切换自动回复。</p>
      </div>
      <dl className="session-meta">
        <dt>会话 ID</dt>
        <dd>{sessionMeta?.id ?? '尚未建立'}</dd>
        <dt>连接状态</dt>
        <dd>{connectionSummary.label}</dd>
        <dt>Session 失效</dt>
        <dd>{sessionMeta?.expires_at ? formatTime(sessionMeta.expires_at) : '--:--'}</dd>
        <dt>总轮次</dt>
        <dd>{stats.totalTurns}</dd>
        <dt>用户消息</dt>
        <dd>{stats.userTurns}</dd>
        <dt>机器人回复</dt>
        <dd>{stats.assistantTurns}</dd>
        <dt>最近更新时间</dt>
        <dd>{formatTime(stats.lastUpdated)}</dd>
      </dl>
      <Toggle
        id="auto-reply-toggle"
        labelText="机器人自动回复"
        labelA="关闭"
        labelB="开启"
        toggled={autoReply}
        onToggle={onToggleAutoReply}
      />
    </Tile>
  );
}
