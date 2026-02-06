import { AppointmentSimulationTest } from '../AppointmentSimulation/AppointmentSimulationTest';
import styles from '../../../pages/TestPage.module.scss';

/**
 * Appointment Tab内容组件
 * 
 * 预约模拟测试功能
 */
export function AppointmentTabContent() {
  return (
    <div className={styles.tabPanelContent}>
      <AppointmentSimulationTest />
    </div>
  );
}
