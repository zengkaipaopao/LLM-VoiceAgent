import React, { useRef, useEffect } from 'react';
import { SkeletonText } from '@carbon/react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation(['pages']);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 空状态
  if (messages.length === 0 && !isLoading) {
    return (
      <div className={styles.emptyState}>
        <p>{t('pages:test.chat.empty.title', 'Start chatting to test the LLM flow')}</p>
        <span className={styles.hint}>
          {t(
            'pages:test.chat.empty.description',
            'Send a message and the assistant will respond in real time.'
          )}
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
