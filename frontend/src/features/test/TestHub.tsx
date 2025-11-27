import { Column, Grid, Tab, TabList, TabPanel, TabPanels, Tabs } from '@carbon/react';
import { PageTitle } from '../../components/atoms/PageTitle';
import { PageSubtitle } from '../../components/atoms/PageSubtitle';
import { DialTest } from './DialTest';
import { AnswerTest } from './AnswerTest';
import { ModelTest } from './ModelTest';


export function TestHub() {
  return (
    <section className="page-section">
      <PageTitle>测试页面</PageTitle>
      <PageSubtitle>用于临时挂载和验证组件。</PageSubtitle>
      <Grid condensed fullWidth>
        <Column sm={4} md={4} lg={12}>
          <Tabs>
            <TabList aria-label="测试标签切换">
              <Tab>拨通测试</Tab>
              <Tab>接听测试</Tab>
              <Tab>模型测试</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <DialTest />
              </TabPanel>
              <TabPanel>
                <AnswerTest />
              </TabPanel>
              <TabPanel>
                <ModelTest />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>
      </Grid>
    </section>
  );
}
