import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  Tabs, 
  TabList, 
  Tab, 
  TabPanels, 
  TabPanel
} from '@carbon/react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { testTabs } from '../config/navigation';
import styles from './TestPage.module.css';

/**
 * TestPage - 实时调试实验室页面
 * 
 * 用于测试Call模拟、WebSocket和Twilio WebCall等链路
 * 
 * 设计特点:
 * - 完全声明式配置，所有Tab内容在 navigation.ts 中定义
 * - 动态生成Tab UI和TabPanel，无需手动维护顺序
 * - 遵循 Carbon Design System Tabs 最佳实践
 */
export function TestPage() {
  const { t } = useTranslation(['pages', 'common']);
  const [searchParams, setSearchParams] = useSearchParams();
  const [enableReviewer, setEnableReviewer] = useState(true);

  // 从 testTabs 动态生成 tabMap
  const tabMap = useMemo(() => testTabs.map(tab => tab.id), []);
  const currentTab = searchParams.get('tab') || tabMap[0];
  const selectedIndex = tabMap.indexOf(currentTab);
  const safeIndex = selectedIndex >= 0 ? selectedIndex : 0;

  const handleTabChange = (event: { selectedIndex: number }) => {
    const newTab = tabMap[event.selectedIndex];
    setSearchParams({ tab: newTab });
  };
  
  // Tab组件通用Props
  const tabComponentProps = {
    enableReviewer,
    onToggle: setEnableReviewer,
  };
  
  return (
    <PageTemplate
      title={t('pages:test.title')}
      subtitle={t('pages:test.subtitle')}
    >
      <Tabs selectedIndex={safeIndex} onChange={handleTabChange}>
        {/* 动态生成 TabList */}
        <TabList 
          aria-label={t('pages:test.tabs.ariaLabel', 'Test Options')}
          contained={false}
        >
          {testTabs.map((tab) => (
            <Tab key={tab.id} renderIcon={tab.icon}>
              {t(`pages:test.tabs.${tab.label}`)}
            </Tab>
          ))}
        </TabList>
        
        {/* 动态生成 TabPanels */}
        <TabPanels>
          {testTabs.map((tab) => {
            const Component = tab.component;
            return (
              <TabPanel key={tab.id}>
                <Component {...tabComponentProps} />
              </TabPanel>
            );
          })}
        </TabPanels>
      </Tabs>
    </PageTemplate>
  );
}
