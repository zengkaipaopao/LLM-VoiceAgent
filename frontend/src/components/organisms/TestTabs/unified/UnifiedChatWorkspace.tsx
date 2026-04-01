import { Tag, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { Message } from '../../../../hooks/useChatStream';
import { ChatInput } from '../../../molecules/ChatInput';
import { MessageList } from '../../MessageList';
import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedChatWorkspaceProps {
  hasSession: boolean;
  sessionClosed: boolean;
  sessionStatus: string;
  messages: Message[];
  isSending: boolean;
  selectedPromptCode: string;
  isStarting: boolean;
  isFinalizing: boolean;
  quickMessages: string[];
  onSendMessage: (value: string) => Promise<void>;
}

export function UnifiedChatWorkspace({
  hasSession,
  sessionClosed,
  sessionStatus,
  messages,
  isSending,
  selectedPromptCode,
  isStarting,
  isFinalizing,
  quickMessages,
  onSendMessage,
}: UnifiedChatWorkspaceProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.chatTile}>
      <div className={styles.chatHeader}>
        <div>
          <h3 className="cds--heading-03">
            {t('pages:test.unified.sections.chatTitle', 'Conversation Workspace')}
          </h3>
          <p className={styles.sectionDescription}>
            {t(
              'pages:test.unified.sections.chatDescription',
              'Send messages to test prompt behavior, action triggering, and extraction quality in one flow.'
            )}
          </p>
        </div>
        <Tag type={sessionClosed ? 'blue' : hasSession ? 'green' : 'warm-gray'}>{sessionStatus}</Tag>
      </div>

      <MessageList messages={messages} isLoading={isSending} />
      <ChatInput
        onSend={(value) => {
          void onSendMessage(value);
        }}
        disabled={!selectedPromptCode || isStarting || isSending || isFinalizing || sessionClosed}
        quickMessages={quickMessages}
        quickMessagesLabel={t('pages:test.unified.chat.quickInputLabel', '快捷输入')}
        placeholder={
          sessionClosed
            ? t(
                'pages:test.unified.chat.closedPlaceholder',
                'This session is closed. Click "New Session" to continue testing.'
              )
            : t(
                'pages:test.unified.chat.inputPlaceholder',
                'Type a message to test prompt behavior and action extraction...'
              )
        }
      />
    </Tile>
  );
}
