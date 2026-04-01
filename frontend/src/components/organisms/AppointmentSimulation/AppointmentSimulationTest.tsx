import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Grid,
  Column,
  Stack,
} from '@carbon/react';

import { ScenarioSelector } from '../../molecules/Simulation/ScenarioSelector';
import { BatchTestControl } from '../../molecules/Simulation/BatchTestControl';
import { SimulationFeedbackPanel } from '../../molecules/Simulation/SimulationFeedbackPanel';
import { useAppointmentSimulationTest } from '../../../hooks/useAppointmentSimulationTest';
import styles from './AppointmentSimulationTest.module.scss';

export const AppointmentSimulationTest: React.FC = () => {
  const { t } = useTranslation(['pages']);
  const {
    scenarios,
    loading,
    result,
    setResult,
    error,
    setError,
    simulateAppointment,
    simulateBatch,
    clearTestData,
  } = useAppointmentSimulationTest();

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.gridContainer}>
        <Column lg={8} md={8} sm={4} className={styles.mainColumn}>
          <ScenarioSelector scenarios={scenarios} onSelect={simulateAppointment} disabled={loading} />
        </Column>

        <Column lg={8} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <BatchTestControl
              onGenerate={simulateBatch}
              onClear={clearTestData}
              loading={loading}
              title={t('pages:test.appointment.batch.title', 'Batch Simulation')}
              description={t(
                'pages:test.appointment.batch.description',
                'Generate multiple appointment events at once.'
              )}
              countLabel={t('pages:test.appointment.batch.countLabel', 'Count')}
              generateButtonText={t(
                'pages:test.appointment.batch.generate',
                'Generate Appointments'
              )}
              clearButtonText={t(
                'pages:test.appointment.batch.clear',
                'Clear Simulated Data'
              )}
            />
          </Stack>
        </Column>
      </Grid>

      <SimulationFeedbackPanel
        loading={loading}
        loadingDescription={t('pages:test.appointment.status.loading', 'Loading...')}
        error={error}
        errorTitle={t('pages:test.appointment.status.errorTitle', 'Error')}
        onDismissError={() => setError(null)}
        result={result}
        successTitle={t('pages:test.appointment.status.successTitle', 'Success')}
        successFallbackMessage={t('pages:test.appointment.status.successTitle', 'Success')}
        onDismissResult={() => setResult(null)}
        responseTitle={t('pages:test.appointment.response', 'Response Data')}
        copyFeedback={t('pages:test.appointment.copyFeedback', 'Copied')}
      />
    </div>
  );
};
