import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { StartTestSessionResponse } from '../../../../api/testLab';
import { PromptTemplate } from '../../../../types/shared';
import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedSessionDetailsPanelProps {
  selectedPrompt: PromptTemplate | undefined;
  session: StartTestSessionResponse | null;
  totalTokens: number;
}

export function UnifiedSessionDetailsPanel({
  selectedPrompt,
  session,
  totalTokens,
}: UnifiedSessionDetailsPanelProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.panelTile}>
      <div>
        <h4 className="cds--heading-01">{t('pages:test.unified.sections.detailsTitle', 'Session Details')}</h4>
        <p className={styles.sectionDescription}>
          {t(
            'pages:test.unified.sections.detailsDescription',
            'Track current model, call metadata, and token usage for this test run.'
          )}
        </p>
      </div>

      {selectedPrompt && (
        <p className={styles.promptInfo}>
          {t('pages:test.unified.meta.currentModel', 'Model: {{provider}}/{{model}} · Temp {{temperature}}', {
            provider: selectedPrompt.llmProvider,
            model: selectedPrompt.llmModel,
            temperature: selectedPrompt.temperature,
          })}
        </p>
      )}

      {session ? (
        <dl className={styles.metaList}>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.unified.meta.callIdLabel', 'Call ID')}</dt>
            <dd>{session.call_id}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.unified.meta.phoneLabel', 'Simulated Phone')}</dt>
            <dd>{session.simulated_phone}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.unified.meta.templateLabel', 'Template')}</dt>
            <dd>{session.template_code}</dd>
          </div>
          <div className={styles.metaRow}>
            <dt>{t('pages:test.unified.meta.tokensLabel', 'Total Tokens')}</dt>
            <dd>{totalTokens}</dd>
          </div>
        </dl>
      ) : (
        <p className={styles.sectionDescription}>
          {t(
            'pages:test.unified.sections.noSession',
            'No active session yet. Start a session to display metadata.'
          )}
        </p>
      )}
    </Tile>
  );
}
