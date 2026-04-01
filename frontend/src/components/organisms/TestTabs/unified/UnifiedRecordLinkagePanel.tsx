import { Button, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { FinalizeTestSessionResponse } from '../../../../api/testLab';
import styles from '../UnifiedTestLabTabContent.module.scss';

interface UnifiedRecordLinkagePanelProps {
  finalizeResult: FinalizeTestSessionResponse | null;
  onViewCalls: () => void;
  onViewAppointments: () => void;
}

export function UnifiedRecordLinkagePanel({
  finalizeResult,
  onViewCalls,
  onViewAppointments,
}: UnifiedRecordLinkagePanelProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.panelTile}>
      <div>
        <h4 className="cds--heading-01">{t('pages:test.unified.records.title', 'Record Linkage')}</h4>
        <p className={styles.sectionDescription}>
          {t(
            'pages:test.unified.records.description',
            'Test data is written to Calls/Appointments and can be reviewed immediately.'
          )}
          {finalizeResult?.appointment_id
            ? t('pages:test.unified.records.currentAppointment', ' Current appointment ID: {{id}}', {
                id: finalizeResult.appointment_id,
              })
            : ''}
        </p>
      </div>

      <div className={styles.buttonGroup}>
        <Button kind="tertiary" size="sm" onClick={onViewCalls}>
          {t('pages:test.unified.actions.viewCalls', 'View Calls')}
        </Button>
        <Button kind="tertiary" size="sm" onClick={onViewAppointments}>
          {t('pages:test.unified.actions.viewAppointments', 'View Appointments')}
        </Button>
      </div>
    </Tile>
  );
}
