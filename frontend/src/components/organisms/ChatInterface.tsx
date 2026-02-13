import React, { useState, useEffect } from 'react';
import { Tile, Select, SelectItem, Button, ActionableNotification, Loading } from '@carbon/react';
import { TrashCan, Download } from '@carbon/icons-react';
import { MessageList } from '../organisms/MessageList';
import { ChatInput } from '../molecules/ChatInput';
import { ExtractionPanel } from '../organisms/ExtractionPanel';
import { useChatStream } from '../../hooks/useChatStream';
import { fetchPrompts } from '../../api/prompts';
import { PromptTemplate } from '../../types/shared';
import styles from './ChatInterface.module.scss';

interface ChatInterfaceProps {
  defaultProvider?: string;
  defaultTemplate?: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  defaultProvider = 'gemini',
  defaultTemplate = 'general_appointment'
}) => {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPromptCode, setSelectedPromptCode] = useState(defaultTemplate);
  const [loadingPrompts, setLoadingPrompts] = useState(true);

  // Load prompts
  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchPrompts();
        setPrompts(data);
        if (data.length > 0 && !data.find(p => p.code === defaultTemplate)) {
             // If default not found, select first
             setSelectedPromptCode(data[0].code);
        }
      } catch (err) {
        console.error("Failed to load prompts", err);
      } finally {
        setLoadingPrompts(false);
      }
    };
    load();
  }, []);

  const selectedPrompt = prompts.find(p => p.code === selectedPromptCode);

  const {
    messages,
    isLoading,
    error,
    callId,
    totalTokens,
    sendMessage,
    retryLastMessage,
    dismissError,
    clearMessages
  } = useChatStream(undefined, selectedPromptCode); // No provider default, let backend handle

  const handleSend = async (content: string) => {
    await sendMessage(content, {
      template_code: selectedPromptCode,
      // No provider/model/temp passed, use backend defaults from template
    });
  };

  const handleExport = () => {
    const data = {
      call_id: callId,
      agent: selectedPrompt?.name,
      template_code: selectedPromptCode,
      total_tokens: totalTokens,
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp.toISOString()
      }))
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${callId || 'new'}.json`;
    a.click();
    URL.revokeObjectURL(url);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={styles.chatInterface}>
      {/* 设置栏 */}
      <Tile className={styles.settingsBar}>
        <div className={styles.settings}>
          {loadingPrompts ? (
             <Loading small withOverlay={false} />
          ) : (
            <Select
                id="agent-select"
                labelText="选择 Agent (提示词模板)"
                value={selectedPromptCode}
                onChange={(e) => setSelectedPromptCode(e.target.value)}
                size="sm"
                helperText={selectedPrompt ? `${selectedPrompt.llmProvider}/${selectedPrompt.llmModel} (T=${selectedPrompt.temperature})` : ""}
            >
                {prompts.map(p => (
                    <SelectItem key={p.id} value={p.code} text={p.name} />
                ))}
            </Select>
          )}

          <div className={styles.actions}>
            <Button
              kind="ghost"
              size="sm"
              renderIcon={Download}
              onClick={handleExport}
              disabled={messages.length === 0}
            >
              导出
            </Button>
            <Button
              kind="danger--ghost"
              size="sm"
              renderIcon={TrashCan}
              onClick={clearMessages}
              disabled={messages.length === 0}
            >
              清空
            </Button>
          </div>
        </div>

        {/* Call ID 和 Token 显示 */}
        {(callId || totalTokens > 0) && (
          <div className={styles.callInfo}>
            {callId && (
              <div className={styles.infoItem}>
                <span className={styles.label}>Call ID:</span>
                <code className={styles.callId}>{callId}</code>
              </div>
            )}
            {totalTokens > 0 && (
              <div className={styles.infoItem}>
                <span className={styles.label}>Total Tokens:</span>
                <span className={styles.tokenCount}>{totalTokens.toLocaleString()}</span>
              </div>
            )}
          </div>
        )}
      </Tile>

      {/* 错误提示和重试 */}
      {error && (
        <ActionableNotification
          kind="error"
          title="错误"
          subtitle={error}
          actionButtonLabel="重试"
          onActionButtonClick={retryLastMessage}
          lowContrast
          hideCloseButton={false}
          onCloseButtonClick={dismissError}
        />
      )}

      {/* 消息列表 */}
      <MessageList messages={messages} isLoading={isLoading} />

      {/* 输入框 */}
      <ChatInput
        onSend={handleSend}
        disabled={isLoading}
        placeholder="输入消息,测试 LLM 对话功能..."
      />

      {/* 提取面板 (仅在有 callId 时显示) */}
      {callId && (
        <ExtractionPanel 
          callId={callId} 
          templateCode={selectedPromptCode}
        />
      )}
    </div>
  );
};
