import { Loading, Select, SelectItem, TextInput } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../../types/shared';
import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedPromptCallerFieldsProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  callerName: string;
  setCallerName: (value: string) => void;
  disabled: boolean;
}

export function UnifiedPromptCallerFields({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  callerName,
  setCallerName,
  disabled,
}: UnifiedPromptCallerFieldsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.formFields}>
      {loadingPrompts ? (
        <Loading small withOverlay={false} />
      ) : (
        <Select
          id="test-lab-prompt"
          labelText={t('pages:test.unified.form.promptLabel', 'Select Prompt Model')}
          value={selectedPromptCode}
          onChange={(event) => setSelectedPromptCode(event.target.value)}
          size="sm"
          disabled={disabled}
        >
          {prompts.map((prompt) => (
            <SelectItem key={prompt.id} value={prompt.code} text={prompt.name} />
          ))}
        </Select>
      )}

      <TextInput
        id="test-lab-caller"
        labelText={t('pages:test.unified.form.callerLabel', 'Simulated Caller Name')}
        value={callerName}
        onChange={(event) => setCallerName(event.target.value)}
        size="sm"
        placeholder={t('pages:test.unified.form.callerPlaceholder', 'Test Caller')}
        disabled={disabled}
      />
    </div>
  );
}
