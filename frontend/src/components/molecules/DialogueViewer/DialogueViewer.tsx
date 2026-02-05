import React, { useMemo } from 'react';
import styles from './DialogueViewer.module.scss';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  ts?: string;
  is_user?: boolean; // legacy support
  text?: string; // legacy support
}

interface DialogueViewerProps {
  rawMessages: any;
}

/**
 * A robust component to parse and display chat dialogue from various JSON formats.
 * Handles strings, nested objects, and arrays.
 */
export const DialogueViewer: React.FC<DialogueViewerProps> = ({ rawMessages }) => {
  const messages = useMemo(() => {
    let result: ChatMessage[] = [];
    
    // Helper to parse string content (handles "obj, obj" pattern)
    const parseString = (str: string): any[] => {
      str = str.trim();
      try {
        return JSON.parse(str);
      } catch (e) {
        // Fallback for comma-separated objects without brackets
        try {
          return JSON.parse(`[${str}]`);
        } catch (e2) {
          console.warn("DialogueViewer: Failed to parse dialogue string:", e);
          return [];
        }
      }
    };

    try {
      if (typeof rawMessages === 'string') {
        result = parseString(rawMessages);
      } else if (rawMessages && typeof rawMessages === 'object') {
        if (Array.isArray(rawMessages)) {
          result = rawMessages;
        } else if (Array.isArray(rawMessages.messages)) {
          result = rawMessages.messages;
        } else if (typeof rawMessages.text === 'string') {
          // Handle case { text: "..." }
          result = parseString(rawMessages.text);
        } else {
          // Fallback: wrap the object itself if it looks like a message
          result = [rawMessages];
        }
      }
    } catch (e) {
      console.error("DialogueViewer: Critical error parsing dialogue:", e);
    }

    if (!Array.isArray(result)) return [];
    return result;
  }, [rawMessages]);

  if (!messages || messages.length === 0) return null;

  return (
    <div className={styles.dialogueContainer}>
      <strong style={{ display: 'block', marginBottom: '0.5rem' }}>详细对话:</strong>
      <div className={styles.messagesList}>
        {messages.map((msg, idx) => {
          // Normalize role
          const role = msg.role || (msg.is_user ? 'user' : 'assistant');
          const isUser = role === 'user';
          // Normalize content
          const content = msg.content || msg.text || JSON.stringify(msg);

          return (
            <div 
              key={idx} 
              className={`${styles.messageRow} ${isUser ? styles.user : styles.assistant}`}
            >
              <div 
                className={`${styles.bubble} ${isUser ? styles.user : styles.assistant}`}
                title={msg.ts || ''}
              >
                <div className={styles.roleLabel}>
                  {isUser ? '用户' : 'AI助手'}
                </div>
                {content}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
