import { Button, Tile } from '@carbon/react';

type AppointmentPanelProps = {
  enabled: boolean;
  message: string | null;
  onCreate: () => void;
  disabled: boolean;
  saving: boolean;
};

export function AppointmentPanel({ enabled, message, onCreate, disabled, saving }: AppointmentPanelProps) {
  if (!enabled) return null;

  return (
    <Tile className="session-panel">
      <div>
        <h3>预约记录</h3>
        <p className="session-panel__helper">将当前对话整理成预约摘要并写入后端记录。</p>
      </div>
      {message && <p className="session-panel__helper">{message}</p>}
      <Button kind="primary" onClick={onCreate} disabled={disabled}>
        {saving ? '生成中...' : '生成预约记录'}
      </Button>
    </Tile>
  );
}
