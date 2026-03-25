import { useTranslation } from 'react-i18next';
import { Tile, Stack, Toggle } from '@carbon/react';
import { WatsonHealthAiStatus } from '@carbon/icons-react';
import styles from './ReviewerTabContent.module.scss';

interface ReviewerTabContentProps {
  enableReviewer: boolean;
  onToggle: (enabled: boolean) => void;
}

/**
 * Reviewer模式Tab内容组件
 * 
 * 用于配置和显示AI Reviewer模式设置
 */
export function ReviewerTabContent({ enableReviewer, onToggle }: ReviewerTabContentProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.reviewerPanel}>
      <Tile>
        <Stack gap={5}>
          <div className={styles.header}>
            <WatsonHealthAiStatus size={24} />
            <h4 className="cds--heading-02">{t('pages:test.reviewer.title')}</h4>
          </div>
          
          <p className="cds--body-01">
            {t('pages:test.reviewer.description')}
          </p>

          <div className={`${styles.reviewerSettings} ${enableReviewer ? styles.reviewerSettingsActive : ''}`}>
            <Toggle
              id="reviewer-toggle"
              labelA={t('pages:test.reviewer.toggle.off')}
              labelB={t('pages:test.reviewer.toggle.on')}
              labelText={t('pages:test.reviewer.toggle.label')}
              toggled={enableReviewer}
              onToggle={onToggle}
              className={styles.toggle}
            />

            {enableReviewer && (
              <div className="cds--label-description">
                <h5 className="cds--label">{t('pages:test.reviewer.logic.title')}</h5>
                <ul className={styles.logicList}>
                  <li><strong>{t('pages:test.simulation.scenarios.ai_handled.title')}:</strong> {t('pages:test.reviewer.logic.ai')}</li>
                  <li><strong>{t('pages:test.simulation.scenarios.transferred.title')}:</strong> {t('pages:test.reviewer.logic.transfer')}</li>
                </ul>
              </div>
            )}
          </div>
        </Stack>
      </Tile>
    </div>
  );
}
