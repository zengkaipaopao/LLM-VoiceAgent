import { useTranslation } from 'react-i18next';
import { Tabs, TabList, Tab, TabPanels, TabPanel } from '@carbon/react';
import { Phone, Network_3, PhoneVoice } from '@carbon/icons-react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { EmptyState } from '../components/organisms/EmptyState';
import { CallSimulationTest } from '../components/CallSimulationTest';

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
  
  return (
    <PageTemplate
      title={t('pages:test.title')}
      subtitle={t('pages:test.subtitle')}
    >
      <Tabs>
        <TabList 
          aria-label="测试功能选项卡"
          contained={false}  // Line tabs - 适合页面级导航
        >
          <Tab renderIcon={Phone}>
            Call Simulation
          </Tab>
          <Tab renderIcon={Network_3}>
            WebSocket
          </Tab>
          <Tab renderIcon={PhoneVoice}>
            Twilio WebCall
          </Tab>
        </TabList>
        
        <TabPanels>
          {/* Call模拟测试 */}
          <TabPanel>
            <div style={{ paddingTop: '1rem' }}>
              <CallSimulationTest />
            </div>
          </TabPanel>
          
          {/* WebSocket测试 */}
          <TabPanel>
            <div style={{ paddingTop: '1rem' }}>
              <EmptyState
                title="WebSocket Test"
                description="WebSocket测试功能开发中..."
                icon={<Network_3 size={48} style={{ color: '#0f62fe' }} />}
              />
            </div>
          </TabPanel>
          
          {/* Twilio测试 */}
          <TabPanel>
            <div style={{ paddingTop: '1rem' }}>
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
