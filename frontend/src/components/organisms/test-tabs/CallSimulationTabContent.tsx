import { CallSimulationTest } from '../../CallSimulationTest';
import styles from '../../../pages/TestPage.module.css';

interface CallSimulationTabContentProps {
  enableReviewer?: boolean;
}

/**
 * Call Simulation Tab内容组件
 * 
 * 包装CallSimulationTest组件并应用正确的样式
 */
export function CallSimulationTabContent({ enableReviewer }: CallSimulationTabContentProps) {
  return (
    <div className={styles.tabPanelContent}>
      <CallSimulationTest enableReviewer={enableReviewer} />
    </div>
  );
}
