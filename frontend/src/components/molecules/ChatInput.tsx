import React, { useState, KeyboardEvent } from 'react';
import { TextArea, Button } from '@carbon/react';
import { Send } from '@carbon/icons-react';
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
  placeholder = '输入消息...',
  quickMessages = [],
  quickMessagesLabel = '快捷输入'
}) => {
  const [input, setInput] = useState('');

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
        placeholder={placeholder}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={3}
        className={styles.textarea}
      />
      
      <div className={styles.footer}>
        <span className={styles.charCount}>
          {input.length} 字符
        </span>
        
        <Button
          kind="primary"
          size="md"
          renderIcon={Send}
          onClick={handleSend}
          disabled={disabled || !input.trim()}
        >
          发送 (Ctrl+Enter)
        </Button>
      </div>

      {quickMessages.length > 0 && (
        <div className={styles.quickSection}>
          <span className={styles.quickLabel}>{quickMessagesLabel}</span>
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
