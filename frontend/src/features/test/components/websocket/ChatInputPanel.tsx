import { FormEvent } from 'react';
import { Button, ContainedList, ContainedListItem, TextArea, Tile } from '@carbon/react';

import { ConnectionState } from './types';

type ChatInputPanelProps = {
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  connectionState: ConnectionState;
  isAssistantTyping: boolean;
  autoReply: boolean;
  onManualReply: () => void;
  quickPrompts: string[];
  onQuickPromptSelect: (value: string) => void;
};

export function ChatInputPanel({
  input,
  onInputChange,
  onSubmit,
  connectionState,
  isAssistantTyping,
  autoReply,
  onManualReply,
  quickPrompts,
  onQuickPromptSelect,
}: ChatInputPanelProps) {
  const disableSend = !input.trim() || connectionState !== 'connected' || isAssistantTyping;
  const disableManualReply = connectionState !== 'connected';

  return (
    <Tile className="ws-input-panel">
      <form className="chat-input-form" onSubmit={onSubmit}>
        <TextArea
          id="test-chat-input"
          labelText="输入测试内容"
          placeholder="例如：请模拟客户提出异议，并帮我迭代回答。"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          rows={5}
          disabled={connectionState !== 'connected'}
        />
        <div className="chat-actions">
          {!autoReply && (
            <Button kind="secondary" type="button" onClick={onManualReply} disabled={disableManualReply}>
              让机器人回复
            </Button>
          )}
          <Button type="submit" disabled={disableSend}>
            发送
          </Button>
        </div>
      </form>
      <ContainedList label="快捷提示" kind="on-page" size="sm" className="ws-quick-prompts-list">
        {quickPrompts.map((item) => (
          <ContainedListItem key={item} onClick={() => onQuickPromptSelect(item)}>
            <span className="ws-quick-prompt-text">{item}</span>
          </ContainedListItem>
        ))}
      </ContainedList>
    </Tile>
  );
}
