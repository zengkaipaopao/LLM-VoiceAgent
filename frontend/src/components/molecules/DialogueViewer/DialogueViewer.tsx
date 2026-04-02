import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import styles from './DialogueViewer.module.scss';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  ts?: string;
  is_user?: boolean; // legacy support
  text?: string; // legacy support
}

interface DialogueViewerProps {
  rawMessages: any;
}

const ASSISTANT_PREFIX_PATTERN =
  /^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*/i;

function normalizeRole(value: unknown): ChatMessage['role'] {
  const raw = String(value ?? '').trim().toLowerCase();
  if (raw === 'system') return 'system';
  if (raw === 'user' || raw === 'human' || raw === 'customer' || raw === '用户') return 'user';
  if (
    raw === 'assistant' ||
    raw === 'ai' ||
    raw === 'bot' ||
    raw === 'model' ||
    raw === '助手' ||
    raw === 'アシスタント'
  ) {
    return 'assistant';
  }
  return 'assistant';
}

function sanitizeAssistantContent(content: string): string {
  return content.replace(ASSISTANT_PREFIX_PATTERN, '').trim();
}

/**
 * A robust component to parse and display chat dialogue from various JSON formats.
 * Handles strings, nested objects, and arrays.
 */
export const DialogueViewer: React.FC<DialogueViewerProps> = ({ rawMessages }) => {
  const { t } = useTranslation(['pages']);
  const messages = useMemo(() => {
    const parseString = (str: string): any => {
      const normalized = str.trim();
      if (!normalized) return null;
      try {
        return JSON.parse(normalized);
      } catch (e) {
        try {
          return JSON.parse(`[${normalized}]`);
        } catch {
          console.warn('DialogueViewer: Failed to parse dialogue string:', e);
          return null;
        }
      }
    };

      const normalizeMessage = (value: any): ChatMessage | null => {
        if (!value || typeof value !== 'object') return null;

        const rawRole = value.role || (value.is_user ? 'user' : 'assistant');
        const role = normalizeRole(rawRole);

        const rawContent = value.content || value.text;
        if (typeof rawContent !== 'string' || !rawContent.trim()) return null;
        const content = role === 'assistant' ? sanitizeAssistantContent(rawContent) : rawContent.trim();
        if (!content) return null;

        return {
          role,
          content,
          ts: typeof value.ts === 'string' ? value.ts : undefined,
        };
      };

    const extractArray = (value: any): any[] => {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value === 'string') {
        const parsed = parseString(value);
        return Array.isArray(parsed) ? parsed : [];
      }
      if (typeof value === 'object') {
        if (Array.isArray(value.conversation)) return value.conversation;
        if (Array.isArray(value.messages)) return value.messages;
        if (Array.isArray(value.raw_messages)) return value.raw_messages;
        if (value.extracted_data) {
          if (Array.isArray(value.extracted_data.conversation)) return value.extracted_data.conversation;
          if (Array.isArray(value.extracted_data.messages)) return value.extracted_data.messages;
        }
      }
      return [];
    };

    try {
      let source: any = rawMessages;
      if (typeof source === 'string') {
        const parsed = parseString(source);
        source = parsed ?? source;
      }

      const candidates = extractArray(source);
      const normalized = candidates
        .map(normalizeMessage)
        .filter((item): item is ChatMessage => !!item)
        .filter((item) => item.role !== 'system');
      if (normalized.length > 0) return normalized;

      // Fallback: render single message when shape is { role, content }.
      const single = normalizeMessage(source);
      if (single && single.role !== 'system') return [single];

      return [];
    } catch (e) {
      console.error('DialogueViewer: Critical error parsing dialogue:', e);
      return [];
    }
  }, [rawMessages]);

  if (!messages || messages.length === 0) return null;

  return (
    <div className={styles.dialogueContainer}>
      <strong style={{ display: 'block', marginBottom: '0.5rem' }}>
        {t('pages:appointments.detailModal.dialogueTitle', 'Dialogue details')}
      </strong>
      <div className={styles.messagesList}>
        {messages.map((msg, idx) => {
          const role = msg.role;
          const isUser = role === 'user';
          const content = msg.content;
          const roleLabel = isUser
            ? t('pages:test.chat.roles.user', 'User')
            : t('pages:test.chat.roles.assistant', 'AI Assistant');

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
                  {roleLabel}
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
