import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../../types/shared';
import styles from '../TwilioTabContent.module.scss';

interface TwilioMetaListProps {
  callSid: string;
  activePrompt: PromptTemplate | undefined;
  useEndpoint: boolean;
  tokenEndpoint: string;
}

export function TwilioMetaList({
  callSid,
  activePrompt,
  useEndpoint,
  tokenEndpoint,
}: TwilioMetaListProps) {
  const { t } = useTranslation(['pages']);

  return (
    <dl className={styles.metaList}>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.twilio.meta.callSid', 'Call SID')}</dt>
        <dd>{callSid || '-'}</dd>
      </div>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.twilio.meta.prompt', 'Selected Prompt')}</dt>
        <dd>{activePrompt ? `${activePrompt.name} (${activePrompt.code})` : '-'}</dd>
      </div>
      <div className={styles.metaRow}>
        <dt>{t('pages:test.twilio.meta.endpoint', 'Token Endpoint')}</dt>
        <dd>{useEndpoint ? tokenEndpoint : t('pages:test.twilio.meta.manualToken', 'Manual token mode')}</dd>
      </div>
    </dl>
  );
}
