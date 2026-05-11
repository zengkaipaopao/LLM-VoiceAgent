import React from 'react';
import { useTranslation } from 'react-i18next';
import { ClickableTile, Grid, Column, Stack } from '@carbon/react';
import styles from './simulation.module.scss';

export interface Scenario {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<any>;
  iconColor: string;
}

interface ScenarioSelectorProps {
  scenarios: Scenario[];
  onSelect: (id: string) => void;
  disabled?: boolean;
}

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({ 
  scenarios, 
  onSelect, 
  disabled = false 
}) => {
  const { t } = useTranslation(['pages']);

  return (
    <Stack gap={6}>
      <section>
        <h4 className={`cds--heading-03 ${styles.sectionTitle}`}>
          {t('pages:test.simulation.scenarios.title')}
        </h4>
        <p className={`cds--body-01 ${styles.sectionDescription}`}>
          {t('pages:test.simulation.scenarios.description', 'Select a scenario to simulate an incoming call.')}
        </p>
        
        <div className={styles.scenarioGrid}>
          {scenarios.map((scenario) => (
            <ClickableTile
              key={scenario.id}
              onClick={() => onSelect(scenario.id)}
              disabled={disabled}
              className={styles.scenarioTile}
            >
              <div className={styles.tileContent}>
                <div className={styles.tileIcon}>
                  <scenario.icon 
                    size={24} 
                    style={{ color: scenario.iconColor }} 
                  />
                </div>
                <div>
                  <h5 className={`cds--heading-compact-01 ${styles.iconWithTitle}`}>
                    {scenario.title}
                  </h5>
                  <p className="cds--body-compact-01 cds--text--secondary">
                    {scenario.description}
                  </p>
                </div>
              </div>
            </ClickableTile>
          ))}
        </div>
      </section>
    </Stack>
  );
};
