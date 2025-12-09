import { InlineLoading, Tag } from '@carbon/react';

import { ChatHistoryProps } from './types';
import { sanitizeAssistantContent } from '../../utils/assistant';

export function ChatHistory({ messages, historyRef, formatTime, isAssistantTyping }: ChatHistoryProps) {
  return (
    <div className="chat-history" ref={historyRef}>
      {messages.map((message) => {
        const displayContent =
          message.role === 'assistant' ? sanitizeAssistantContent(message.content) : message.content;
        if (message.role === 'assistant' && !displayContent) {
          return null;
        }
        return (
          <div
            key={message.id}
            className={`chat-bubble ${message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}
          >
            <div className="chat-meta">
              <Tag type={message.role === 'user' ? 'blue' : 'purple'} size="sm">
                {message.role === 'user' ? '我' : '机器人'}
              </Tag>
              <span>{formatTime(message.timestamp)}</span>
              {message.streaming && message.role === 'assistant' && (
                <InlineLoading status="active" description="生成中" />
              )}
            </div>
            <div className="chat-content">{displayContent}</div>
          </div>
        );
      })}
      {isAssistantTyping && !messages.some((msg) => msg.streaming) && (
        <div className="chat-bubble chat-bubble-assistant">
          <div className="chat-meta">
            <Tag type="purple" size="sm">
              机器人
            </Tag>
            <InlineLoading status="active" description="思考中" />
          </div>
        </div>
      )}
    </div>
  );
}
