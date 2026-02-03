import { useState } from 'react';
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
  const [enableReviewer, setEnableReviewer] = useState(true);
  
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
          <Tab renderIcon={WatsonHealthAiStatus}>
            Reviewer Mode
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
              <CallSimulationTest enableReviewer={enableReviewer} />
            </div>
          </TabPanel>
          
          {/* Reviewer模式设置 */}
          <TabPanel>
             <div style={{ paddingTop: '1rem', maxWidth: '800px' }}>
                <Tile>
                  <Stack gap={5}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <WatsonHealthAiStatus size={24} />
                        <h4 className="cds--heading-02">AI 审查员模式 (Reviewer Mode)</h4>
                    </div>
                    
                    <p className="cds--body-01">
                      开启审查员模式后，系统会在通话结束后自动调用 LLM 对通话质量、用户情绪和解决率进行评估。
                      这将生成"信赖度"分数和详细的通话摘要。此设置将应用于"Call Simulation"中的所有测试用例。
                    </p>

                    <div style={{ 
                      padding: '1rem', 
                      backgroundColor: enableReviewer ? 'var(--cds-layer-01)' : 'transparent',
                      border: enableReviewer ? '1px solid var(--cds-border-subtle)' : 'none'
                    }}>
                      <Toggle
                        id="reviewer-toggle"
                        labelA="已关闭"
                        labelB="已开启"
                        labelText="启用自动评估"
                        toggled={enableReviewer}
                        onToggle={(checked) => setEnableReviewer(checked)}
                        style={{ marginBottom: '1rem' }}
                      />

                      {enableReviewer && (
                        <div className="cds--label-description">
                           <h5 className="cds--label">模拟评分逻辑</h5>
                          <ul style={{ listStyleType: 'disc', paddingLeft: '1rem', marginTop: '0.5rem' }}>
                            <li><strong>AI处理:</strong> 随机生成 85-100 分</li>
                            <li><strong>人工转接:</strong> 随机生成 60-80 分</li>
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
