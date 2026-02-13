import React, { useRef, useEffect } from 'react';
import { SkeletonText } from '@carbon/react';
import { MessageBubble } from '../molecules/MessageBubble';
import type { Message } from '../../hooks/useChatStream';
import styles from './MessageList.module.scss';

/**
 * MessageList Props
 */
interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

/**
 * MessageList - 消息列表组件
 * 
 * 功能:
 * - 显示所有对话消息
 * - 自动滚动到最新消息
 * - Loading 状态显示
 * - 空状态提示
 */
export const MessageList: React.FC<MessageListProps> = ({ 
  messages, 
  isLoading = false 
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 空状态
  if (messages.length === 0 && !isLoading) {
    return (
      <div className={styles.emptyState}>
        <p>开始对话,测试 LLM 功能</p>
        <span className={styles.hint}>
          输入消息并发送,AI 助手将实时回复
        </span>
      </div>
    );
  }

  return (
    <div className={styles.messageList}>
      {messages.map((message, index) => (
        <MessageBubble key={index} message={message} />
      ))}
      
      {/* Loading 状态 */}
      {isLoading && (
        <div className={styles.loadingIndicator}>
          <SkeletonText heading={false} lineCount={2} width="60%" />
        </div>
      )}
      
      {/* 滚动锚点 */}
      <div ref={messagesEndRef} />
    </div>
  );
};
