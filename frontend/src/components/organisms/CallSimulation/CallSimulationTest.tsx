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
import { useCallSimulationTest } from '../../../hooks/useCallSimulationTest';
import styles from './CallSimulationTest.module.scss';

interface CallSimulationTestProps {
  enableReviewer: boolean;
}

export const CallSimulationTest: React.FC<CallSimulationTestProps> = ({ enableReviewer }) => {
  const { t } = useTranslation(['pages']);
  const {
    scenarios,
    loading,
    result,
    setResult,
    error,
    setError,
    simulateCall,
    simulateBatch,
    clearTestData,
  } = useCallSimulationTest(enableReviewer);

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.gridContainer}>
        <Column lg={8} md={8} sm={4} className={styles.mainColumn}>
          <ScenarioSelector scenarios={scenarios} onSelect={simulateCall} disabled={loading} />
        </Column>

        <Column lg={8} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <BatchTestControl
              onGenerate={simulateBatch}
              onClear={clearTestData}
              loading={loading}
              description={t('pages:test.simulation.batch.description', {
                status: enableReviewer
                  ? t('pages:test.simulation.batch.on')
                  : t('pages:test.simulation.batch.off'),
              })}
            />
          </Stack>
        </Column>
      </Grid>

      <SimulationFeedbackPanel
        loading={loading}
        loadingDescription={t('pages:test.simulation.status.loading')}
        error={error}
        errorTitle={t('pages:test.simulation.status.error')}
        onDismissError={() => setError(null)}
        result={result}
        successTitle={t('pages:test.simulation.status.success')}
        successFallbackMessage={t('pages:test.simulation.status.success')}
        onDismissResult={() => setResult(null)}
        responseTitle={t('pages:test.simulation.response')}
        copyFeedback={t('pages:test.simulation.copyFeedback', '已复制')}
      />
    </div>
  );
};

export default CallSimulationTest;
