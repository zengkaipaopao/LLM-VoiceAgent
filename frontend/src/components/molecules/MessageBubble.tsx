import React from 'react';
import { Tile } from '@carbon/react';
import { User, WatsonHealthAiStatus } from '@carbon/icons-react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../../hooks/useChatStream';
import styles from './MessageBubble.module.scss';

/**
 * MessageBubble Props
 */
interface MessageBubbleProps {
  message: Message;
}

/**
 * MessageBubble - 对话消息气泡组件
 * 
 * 功能:
 * - 显示用户/助手消息
 * - 支持 Markdown 渲染
 * - 区分不同角色的样式
 */
export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const { t, i18n } = useTranslation(['pages']);
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // 系统消息特殊处理
  if (isSystem) {
    return (
      <div className={styles.systemMessage}>
        <p>{message.content}</p>
      </div>
    );
  }

  return (
    <div className={`${styles.messageBubble} ${isUser ? styles.user : styles.assistant}`}>
      <div className={styles.messageHeader}>
        <div className={styles.avatar}>
          {isUser ? (
            <User size={20} />
          ) : (
            <WatsonHealthAiStatus size={20} />
          )}
        </div>
        <span className={styles.role}>
          {isUser
            ? t('pages:test.chat.roles.user', 'User')
            : t('pages:test.chat.roles.assistant', 'AI Assistant')}
        </span>
        <span className={styles.timestamp}>
          {message.timestamp.toLocaleTimeString(i18n.language || undefined, {
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </span>
      </div>
      
      <Tile className={styles.messageContent}>
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        )}
      </Tile>
    </div>
  );
};
