import { useEffect, useMemo, useState } from 'react';
import { Column, Dropdown, Grid, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from '@carbon/react';
import { PageSubtitle } from '../../components/atoms/PageSubtitle';
import { PageTitle } from '../../components/atoms/PageTitle';
import { WebSocketConsole } from './components/WebSocketConsole';
import { WebRtcConsole } from './components/WebRtcConsole';
import { SipConsole } from './components/SipConsole';
import { useAppState } from '../../state/AppStateContext';
import { PromptTemplate } from '../../types';

export function TestHub() {
  const { prompts } = useAppState();
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(() => prompts[0]?.id ?? null);

  const selectedPrompt = useMemo<PromptTemplate | undefined>(() => {
    if (!prompts.length) {
      return undefined;
    }
    return prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0];
  }, [prompts, selectedPromptId]);

  useEffect(() => {
    if (!selectedPrompt && prompts.length) {
      setSelectedPromptId(prompts[0].id);
    }
  }, [prompts, selectedPrompt]);

  return (
    <section className="page-section">
      <PageTitle>实时调试实验室</PageTitle>
      <PageSubtitle>在单一界面体验 WebSocket、WebRTC 与 SIP 三种 Realtime 工作流，方便比对链路。</PageSubtitle>
      <Grid condensed fullWidth>
        <Column sm={4} md={8} lg={12}>
          <Tile className="prompt-selector">
            <Dropdown
              id="prompt-selector"
              titleText="测试 Prompt"
              label="选择 Prompt"
              items={prompts}
              itemToString={(item) => (item ? `${item.name} · ${item.modelId}` : '')}
              selectedItem={selectedPrompt ?? null}
              onChange={({ selectedItem }) =>
                setSelectedPromptId((selectedItem as PromptTemplate | null)?.id ?? null)
              }
            />
          </Tile>
        </Column>
        <Column sm={4} md={8} lg={12}>
          <Tabs className="test-tabs">
            <TabList aria-label="测试架构选择">
              <Tab>WebSocket</Tab>
              <Tab>WebRTC</Tab>
              <Tab>SIP</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <WebSocketConsole prompt={selectedPrompt} />
              </TabPanel>
              <TabPanel>
                <WebRtcConsole prompt={selectedPrompt} />
              </TabPanel>
              <TabPanel>
                <SipConsole prompt={selectedPrompt} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>
      </Grid>
    </section>
  );
}
