import { ContainedList, ContainedListItem, Tile, Toggle } from '@carbon/react';

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
      <ContainedList label="会话概览" kind="on-page" size="sm" className="session-info-list" isInset>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">会话 ID</span>
            <span className="session-info-value">{sessionMeta?.id ?? '尚未建立'}</span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">连接状态</span>
            <span className="session-info-value">{connectionSummary.label}</span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">Session 失效</span>
            <span className="session-info-value">
              {sessionMeta?.expires_at ? formatTime(sessionMeta.expires_at) : '--:--'}
            </span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">总轮次</span>
            <span className="session-info-value">{stats.totalTurns}</span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">用户消息</span>
            <span className="session-info-value">{stats.userTurns}</span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">机器人回复</span>
            <span className="session-info-value">{stats.assistantTurns}</span>
          </div>
        </ContainedListItem>
        <ContainedListItem>
          <div className="session-info-row">
            <span className="session-info-label">最近更新时间</span>
            <span className="session-info-value">{formatTime(stats.lastUpdated)}</span>
          </div>
        </ContainedListItem>
      </ContainedList>
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
