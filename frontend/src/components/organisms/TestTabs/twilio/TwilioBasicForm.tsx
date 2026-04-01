import { InlineLoading, Select, SelectItem, TextInput } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../../types/shared';
import styles from '../TwilioTabContent.module.scss';

interface TwilioBasicFormProps {
  identity: string;
  setIdentity: (value: string) => void;
  toNumber: string;
  setToNumber: (value: string) => void;
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
}

export function TwilioBasicForm({
  identity,
  setIdentity,
  toNumber,
  setToNumber,
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
}: TwilioBasicFormProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.formGrid}>
      <TextInput
        id="twilio-identity"
        labelText={t('pages:test.twilio.form.identity', 'Client Identity')}
        value={identity}
        onChange={(event) => setIdentity(event.target.value)}
        placeholder="webcall-tester"
      />
      <TextInput
        id="twilio-dial-number"
        labelText={t('pages:test.twilio.form.toNumber', 'Target Number (E.164)')}
        value={toNumber}
        onChange={(event) => setToNumber(event.target.value)}
        placeholder="+819012345678"
      />
      {loadingPrompts ? (
        <InlineLoading description={t('pages:test.twilio.loading.prompts', 'Loading prompts...')} />
      ) : (
        <Select
          id="twilio-prompt-code"
          labelText={t('pages:test.twilio.form.prompt', 'Prompt Template')}
          value={selectedPromptCode}
          onChange={(event) => setSelectedPromptCode(event.target.value)}
        >
          {prompts.map((prompt) => (
            <SelectItem key={prompt.id} value={prompt.code} text={prompt.name} />
          ))}
        </Select>
      )}
    </div>
  );
}
