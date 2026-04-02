import React from 'react';
import { useTranslation } from 'react-i18next';

import { ChatErrorNotification } from '../molecules/ChatInterface';
import { ChatControlPanel } from './ChatInterface/ChatControlPanel';
import { MessageList } from './MessageList';
import { ChatInput } from '../molecules/ChatInput';
import { ExtractionPanel } from './ExtractionPanel';
import { useChatInterfaceState } from '../../hooks/useChatInterfaceState';
import styles from './ChatInterface.module.scss';

interface ChatInterfaceProps {
  defaultProvider?: string;
  defaultTemplate?: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  defaultProvider = 'gemini',
  defaultTemplate = 'general_appointment',
}) => {
  void defaultProvider;
  const { t } = useTranslation(['pages']);

  const {
    prompts,
    selectedPromptCode,
    setSelectedPromptCode,
    selectedPrompt,
    loadingPrompts,
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    handleSend,
    handleExport,
    retryLastMessage,
    dismissError,
    clearMessages,
  } = useChatInterfaceState({ defaultTemplate });

  return (
    <div className={styles.chatInterface}>
      <ChatControlPanel
        loadingPrompts={loadingPrompts}
        prompts={prompts}
        selectedPromptCode={selectedPromptCode}
        selectedPrompt={selectedPrompt}
        callId={callId}
        totalTokens={totalTokens}
        hasMessages={messages.length > 0}
        onPromptChange={setSelectedPromptCode}
        onExport={handleExport}
        onClear={clearMessages}
      />

      <ChatErrorNotification
        error={error}
        onRetry={retryLastMessage}
        onDismiss={dismissError}
      />

      <MessageList messages={messages} isLoading={isLoading} />

      <ChatInput
        onSend={handleSend}
        disabled={isLoading}
        placeholder={t('pages:test.chat.input.placeholder', 'Type a message...')}
      />

      {callId && <ExtractionPanel callId={callId} templateCode={selectedPromptCode} />}
    </div>
  );
};
