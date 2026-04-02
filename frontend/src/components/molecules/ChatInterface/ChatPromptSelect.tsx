import { Loading, Select, SelectItem } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation(['pages']);

  if (loading) {
    return <Loading small withOverlay={false} />;
  }

  return (
    <div className={styles.container}>
      <Select
        id="agent-select"
        labelText={t('pages:test.chat.promptSelector.label', 'Select Agent (prompt template)')}
        value={selectedPromptCode}
        onChange={(event) => onChange(event.target.value)}
        size="sm"
        helperText={
          selectedPrompt
            ? t('pages:test.chat.promptSelector.helper', {
                provider: selectedPrompt.llmProvider,
                model: selectedPrompt.llmModel,
                temperature: selectedPrompt.temperature,
                defaultValue: '{{provider}}/{{model}} (T={{temperature}})',
              })
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
