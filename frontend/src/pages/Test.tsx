import { Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from '@carbon/react';
import { PageTemplate } from '../components/templates/PageTemplate';
import { normalizeTestTabId, testTabs } from '../config/navigation';
import { testTabComponents } from '../features/test-lab/registry';
import styles from './Test.module.scss';

/**
 * TestPage - 实时调试实验室页面
 * 
 * 用于文字测试、语音测试与审查链路调试
 * 
 * 设计特点:
 * - navigation.ts 只负责导航元数据，真实 Tab 组件按需懒加载
 * - 动态生成 Tab UI 和 TabPanel，无需手动维护顺序
 * - 保留旧 query tab 参数兼容，但统一收口到 text / voice / reviewer
 */
export function Test() {
  const { t } = useTranslation(['pages', 'common']);
  const [searchParams, setSearchParams] = useSearchParams();
  const [enableReviewer, setEnableReviewer] = useState(true);

  const tabMap = useMemo(() => testTabs.map(tab => tab.id), []);
  const currentTab = normalizeTestTabId(searchParams.get('tab') || tabMap[0]);
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
          {testTabs.map((tab, index) => {
            const Component = testTabComponents[tab.id];
            return (
              <TabPanel key={tab.id}>
                <div className={styles.tabPanelContent}>
                  {safeIndex === index ? (
                    <Suspense fallback={<div>{t('common:status.loading')}</div>}>
                      <Component {...tabComponentProps} />
                    </Suspense>
                  ) : null}
                </div>
              </TabPanel>
            );
          })}
        </TabPanels>
      </Tabs>
    </PageTemplate>
  );
}
