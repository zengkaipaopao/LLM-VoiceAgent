import { Loading, Select, SelectItem } from '@carbon/react';

import { PromptTemplate } from '../../../types/shared';
import styles from './ChatPromptSelect.module.scss';

interface ChatPromptSelectProps {
  loading: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  selectedPrompt?: PromptTemplate;
  onChange: (promptCode: string) => void;
}

export function ChatPromptSelect({
  loading,
  prompts,
  selectedPromptCode,
  selectedPrompt,
  onChange,
}: ChatPromptSelectProps) {
  if (loading) {
    return <Loading small withOverlay={false} />;
  }

  return (
    <div className={styles.container}>
      <Select
        id="agent-select"
        labelText="选择 Agent (提示词模板)"
        value={selectedPromptCode}
        onChange={(event) => onChange(event.target.value)}
        size="sm"
        helperText={
          selectedPrompt
            ? `${selectedPrompt.llmProvider}/${selectedPrompt.llmModel} (T=${selectedPrompt.temperature})`
            : ''
        }
      >
        {prompts.map((prompt) => (
          <SelectItem key={prompt.id} value={prompt.code} text={prompt.name} />
        ))}
      </Select>
    </div>
  );
}
