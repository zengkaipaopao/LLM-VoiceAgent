import { InlineLoading, Select, SelectItem } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../../types/shared';

interface WebSocketPromptTemplateSelectProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  disabled: boolean;
  lockToTemplate: boolean;
}

export function WebSocketPromptTemplateSelect({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  disabled,
  lockToTemplate,
}: WebSocketPromptTemplateSelectProps) {
  const { t } = useTranslation(['pages']);

  if (loadingPrompts) {
    return (
      <InlineLoading
        description={t('pages:test.websocket.form.loadingPrompts', 'Loading prompts...')}
      />
    );
  }

  return (
    <Select
      id="live-prompt-template"
      labelText={t('pages:test.websocket.form.promptTemplate', 'Prompt Template')}
      value={selectedPromptCode}
      onChange={(event) => setSelectedPromptCode(event.target.value)}
      disabled={disabled}
    >
      {!lockToTemplate && (
        <SelectItem
          value=""
          text={t('pages:test.websocket.form.noPrompt', 'No prompt (manual instruction)')}
        />
      )}
      {prompts.map((prompt) => (
        <SelectItem key={prompt.id} value={prompt.code} text={`${prompt.name} (${prompt.code})`} />
      ))}
    </Select>
  );
}
