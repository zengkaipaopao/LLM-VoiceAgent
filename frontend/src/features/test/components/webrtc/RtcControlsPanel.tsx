import { Button, InlineLoading, TextArea, Tile } from '@carbon/react';
import { RefObject } from 'react';

type RtcControlsPanelProps = {
  audioRef: RefObject<HTMLAudioElement>;
  command: string;
  onCommandChange: (value: string) => void;
  onSendCommand: () => void;
  commandDisabled: boolean;
  error?: string | null;
};

export function RtcControlsPanel({
  audioRef,
  command,
  onCommandChange,
  onSendCommand,
  commandDisabled,
  error,
}: RtcControlsPanelProps) {
  return (
    <Tile className="rtc-controls-panel">
      <div className="rtc-audio-preview">
        <div>
          <h4>远端 Audio 输出</h4>
          <p>允许浏览器播放声音即可听到机器人语音。</p>
        </div>
        <audio ref={audioRef} controls autoPlay className="rtc-audio-element" />
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
            onChange={(event) => onCommandChange(event.target.value)}
            placeholder='{ "type": "input_text", "text": "请重复上一句" }'
            disabled={commandDisabled}
          />
          <Button type="button" onClick={onSendCommand} disabled={commandDisabled || !command.trim()}>
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
  );
}
