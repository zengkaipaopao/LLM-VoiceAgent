import React, { useState, KeyboardEvent } from 'react';
import { TextArea, Button } from '@carbon/react';
import { Send } from '@carbon/icons-react';
import { useTranslation } from 'react-i18next';
import styles from './ChatInput.module.scss';

/**
 * ChatInput Props
 */
interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  quickMessages?: string[];
  quickMessagesLabel?: string;
}

/**
 * ChatInput - 对话输入框组件
 * 
 * 功能:
 * - 多行文本输入
 * - 发送按钮
 * - 快捷键支持 (Ctrl+Enter)
 * - 字符计数
 */
export const ChatInput: React.FC<ChatInputProps> = ({ 
  onSend, 
  disabled = false,
  placeholder,
  quickMessages = [],
  quickMessagesLabel
}) => {
  const { t } = useTranslation(['pages']);
  const [input, setInput] = useState('');
  const resolvedPlaceholder =
    placeholder ?? t('pages:test.chat.input.placeholder', 'Type a message...');
  const resolvedQuickMessagesLabel =
    quickMessagesLabel ?? t('pages:test.chat.input.quickLabel', 'Quick input');

  const handleSend = () => {
    const trimmed = input.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter 或 Cmd+Enter 发送
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.chatInput}>
      <TextArea
        id="chat-input"
        labelText=""
        placeholder={resolvedPlaceholder}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={3}
        className={styles.textarea}
      />
      
      <div className={styles.footer}>
        <span className={styles.charCount}>
          {t('pages:test.chat.input.charCount', {
            count: input.length,
            defaultValue: '{{count}} chars',
          })}
        </span>
        
        <Button
          kind="primary"
          size="md"
          renderIcon={Send}
          onClick={handleSend}
          disabled={disabled || !input.trim()}
        >
          {t('pages:test.chat.input.send', 'Send (Ctrl+Enter)')}
        </Button>
      </div>

      {quickMessages.length > 0 && (
        <div className={styles.quickSection}>
          <span className={styles.quickLabel}>{resolvedQuickMessagesLabel}</span>
          <div className={styles.quickButtons}>
            {quickMessages.map((message) => (
              <button
                key={message}
                type="button"
                className={styles.quickButton}
                disabled={disabled}
                onClick={() => setInput(message)}
                title={message}
              >
                {message}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
