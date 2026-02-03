import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Tabs, 
  TabList, 
  Tab, 
  TabPanels, 
  TabPanel, 
  Tile,
  Stack,
  Toggle,
  Grid,
  Column
} from '@carbon/react';
import { 
  Phone, 
  Network_3, 
  PhoneVoice,
  WatsonHealthAiStatus 
} from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';
import { CallSimulationTest } from '../components/CallSimulationTest';
import styles from './TestPage.module.css';

/**
 * TestPage - 实时调试实验室页面
 * 
 * 用于测试Call模拟、WebSocket和Twilio WebCall等链路
 * 
 * 遵循 Carbon Design System Tabs 最佳实践:
 * - 使用图标增强可识别性
 * - Line tabs 适合页面级导航
 * - 清晰的 aria-label 提升可访问性
 */
export function TestPage() {
  const { t } = useTranslation(['pages', 'common']);
  const [searchParams, setSearchParams] = useSearchParams();
  const [enableReviewer, setEnableReviewer] = useState(true);

  // Define tab mapping to sync with SideNav
  const tabMap = ['call-simulation', 'reviewer', 'websocket', 'twilio'];
  const currentTab = searchParams.get('tab') || 'call-simulation';
  const selectedIndex = tabMap.indexOf(currentTab);
  const safeIndex = selectedIndex >= 0 ? selectedIndex : 0;

  const handleTabChange = (event: { selectedIndex: number }) => {
    const newTab = tabMap[event.selectedIndex];
    setSearchParams({ tab: newTab });
  };
  
  return (
    <PageTemplate
      title={t('pages:test.title')}
      subtitle={t('pages:test.subtitle')}
    >
      <Tabs selectedIndex={safeIndex} onChange={handleTabChange}>
        <TabList 
          aria-label={t('pages:test.tabs.ariaLabel', 'Test Options')}
          contained={false}  // Line tabs - 适合页面级导航
        >
          <Tab renderIcon={Phone}>
            {t('pages:test.tabs.simulation')}
          </Tab>
          <Tab renderIcon={WatsonHealthAiStatus}>
            {t('pages:test.tabs.reviewer')}
          </Tab>
          <Tab renderIcon={Network_3}>
            {t('pages:test.tabs.websocket')}
          </Tab>
          <Tab renderIcon={PhoneVoice}>
            {t('pages:test.tabs.twilio')}
          </Tab>
        </TabList>
        
        <TabPanels>
          {/* Call模拟测试 */}
          <TabPanel>
            <div className={styles.tabPanelContent}>
              <CallSimulationTest enableReviewer={enableReviewer} />
            </div>
          </TabPanel>
          
          {/* Reviewer模式设置 */}
          <TabPanel>
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
                        onToggle={(checked) => setEnableReviewer(checked)}
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
          </TabPanel>
          {/* WebSocket测试 */}
          <TabPanel>
            <div className={styles.tabPanelContent}>
              <EmptyState
                title="WebSocket Test"
                description="WebSocket测试功能开发中..."
                icon={<Network_3 size={48} style={{ color: '#0f62fe' }} />}
              />
            </div>
          </TabPanel>
          
          {/* Twilio测试 */}
          <TabPanel>
            <div className={styles.tabPanelContent}>
              <EmptyState
                title="Twilio WebCall Test"
                description="Twilio WebCall测试功能开发中..."
                icon={<PhoneVoice size={48} style={{ color: '#0f62fe' }} />}
              />
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </PageTemplate>
  );
}
