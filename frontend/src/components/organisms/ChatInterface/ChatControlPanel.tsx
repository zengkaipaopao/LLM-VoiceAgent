import { Tile } from '@carbon/react';

import {
  ChatActionButtons,
  ChatPromptSelect,
  ChatSessionMeta,
} from '../../molecules/ChatInterface';
import { PromptTemplate } from '../../../types/shared';
import styles from './ChatControlPanel.module.scss';

interface ChatControlPanelProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  selectedPrompt?: PromptTemplate;
  callId: string | null;
  totalTokens: number;
  hasMessages: boolean;
  onPromptChange: (promptCode: string) => void;
  onExport: () => void;
  onClear: () => void;
}

export function ChatControlPanel({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  selectedPrompt,
  callId,
  totalTokens,
  hasMessages,
  onPromptChange,
  onExport,
  onClear,
}: ChatControlPanelProps) {
  return (
    <Tile className={styles.settingsBar}>
      <div className={styles.settings}>
        <ChatPromptSelect
          loading={loadingPrompts}
          prompts={prompts}
          selectedPromptCode={selectedPromptCode}
          selectedPrompt={selectedPrompt}
          onChange={onPromptChange}
        />

        <ChatActionButtons hasMessages={hasMessages} onExport={onExport} onClear={onClear} />
      </div>

      <ChatSessionMeta callId={callId} totalTokens={totalTokens} />
    </Tile>
  );
}
