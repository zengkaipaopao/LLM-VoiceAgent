import { Column, Grid, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from '@carbon/react';

export function TestPage() {
  return (
    <section className="page-section">
      <h1 className="page-title">测试页面</h1>
      <p className="page-subtitle">用于临时挂载和验证组件。</p>
      <Grid condensed fullWidth>
        <Column sm={4} md={4} lg={12}>
          {/* Carbon Tabs skeleton: TabList + TabPanels 必须成对出现 */}
          <Tabs>
            <TabList aria-label="测试标签切换">
              <Tab>拨通测试</Tab>
              <Tab>接听测试</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>内容 1</TabPanel>
              <TabPanel>内容 2</TabPanel>
            </TabPanels>
          </Tabs>
        </Column>
      </Grid>
    </section>
  );
}
