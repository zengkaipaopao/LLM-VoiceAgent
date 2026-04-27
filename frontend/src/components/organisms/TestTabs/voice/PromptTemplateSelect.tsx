import { Select, SelectItem } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../../types/shared';

interface PromptTemplateSelectProps {
  id: string;
  labelText: string;
  value: string;
  prompts: PromptTemplate[];
  loading: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
}

export function PromptTemplateSelect({
  id,
  labelText,
  value,
  prompts,
  loading,
  disabled = false,
  onChange,
}: PromptTemplateSelectProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Select
      id={id}
      labelText={labelText}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled || loading || prompts.length === 0}
    >
      {prompts.length === 0 && (
        <SelectItem
          value=""
          text={
            loading
              ? t('pages:test.voiceLab.promptSelect.loading', 'Loading...')
              : t('pages:test.voiceLab.promptSelect.empty', 'No prompts available')
          }
        />
      )}
      {prompts.map((prompt) => (
        <SelectItem key={prompt.id} value={prompt.code} text={`${prompt.name} (${prompt.code})`} />
      ))}
    </Select>
  );
}
