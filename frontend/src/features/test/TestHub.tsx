import { useEffect, useMemo, useState } from 'react';
import { Column, Dropdown, Grid, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from '@carbon/react';
import { PageSubtitle } from '../../components/atoms/PageSubtitle';
import { PageTitle } from '../../components/atoms/PageTitle';
import { WebSocketConsole } from './components/WebSocketConsole';
import { WebRtcConsole } from './components/WebRtcConsole';
import { SipConsole } from './components/SipConsole';
import { TwilioWebCallPanel } from './components/TwilioWebCallPanel';
import { useAppState } from '../../state/AppStateContext';
import { PromptTemplate } from '../../types';

const PROMPT_STORAGE_KEY = 'testHub.selectedPromptId';

export function TestHub() {
  const { prompts, loadPrompts, promptsLoaded, loadingPrompts } = useAppState();
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [activeTabIndex, setActiveTabIndex] = useState(0);

  useEffect(() => {
    if (!promptsLoaded && !loadingPrompts) {
      void loadPrompts();
    }
  }, [loadPrompts, loadingPrompts, promptsLoaded]);

  const selectedPrompt = useMemo<PromptTemplate | undefined>(() => {
    if (!prompts.length) {
      return undefined;
    }
    return prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0];
  }, [prompts, selectedPromptId]);

  useEffect(() => {
    if (!prompts.length) return;
    if (typeof window === 'undefined') {
      setSelectedPromptId((prev) => (prev && prompts.some((prompt) => prompt.id === prev) ? prev : prompts[0]?.id ?? null));
      return;
    }
    setSelectedPromptId((prev) => {
      if (prev && prompts.some((prompt) => prompt.id === prev)) {
        return prev;
      }
      try {
        const stored = window.localStorage.getItem(PROMPT_STORAGE_KEY);
        if (stored && prompts.some((prompt) => prompt.id === stored)) {
          return stored;
        }
      } catch (error) {
        console.warn('读取 Prompt 选择缓存失败', error);
      }
      return prompts[0]?.id ?? null;
    });
  }, [prompts]);

  useEffect(() => {
    if (!selectedPromptId) return;
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(PROMPT_STORAGE_KEY, selectedPromptId);
    } catch (error) {
      console.warn('保存 Prompt 选择缓存失败', error);
    }
  }, [selectedPromptId]);

  return (
    <section className="page-section">
      <PageTitle>实时调试实验室</PageTitle>
      <PageSubtitle>在单一界面体验 WebSocket、WebRTC、SIP 以及 Twilio WebCall 等链路，方便比对。</PageSubtitle>
      {!promptsLoaded && <p>Prompt 列表加载中...</p>}
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
          <Tabs
            className="test-tabs"
            selectedIndex={activeTabIndex}
            onChange={({ selectedIndex }) => setActiveTabIndex(selectedIndex)}
          >
            <TabList aria-label="测试架构选择">
              <Tab>WebSocket</Tab>
              <Tab>WebRTC</Tab>
              <Tab>SIP</Tab>
              <Tab>Twilio WebCall</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                {activeTabIndex === 0 ? <WebSocketConsole prompt={selectedPrompt} /> : null}
              </TabPanel>
              <TabPanel>
                {activeTabIndex === 1 ? <WebRtcConsole prompt={selectedPrompt} /> : null}
              </TabPanel>
              <TabPanel>
                {activeTabIndex === 2 ? <SipConsole prompt={selectedPrompt} /> : null}
              </TabPanel>
              <TabPanel>
                {activeTabIndex === 3 ? <TwilioWebCallPanel prompt={selectedPrompt} /> : null}
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>
      </Grid>
    </section>
  );
}
