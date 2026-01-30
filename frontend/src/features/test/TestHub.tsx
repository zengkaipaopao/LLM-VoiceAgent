import { useEffect, useMemo, useState } from 'react';
import { Column, Dropdown, DropdownSkeleton, Grid, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from '@carbon/react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageSubtitle } from '../../components/atoms/PageSubtitle';
import { PageTitle } from '../../components/atoms/PageTitle';
import { WebSocketConsole } from './components/WebSocketConsole';
import { TwilioWebCallPanel } from './components/TwilioWebCallPanel';
import { usePromptsQuery } from '../../api/hooks';
import { PromptTemplate } from '../../types';

const PROMPT_STORAGE_KEY = 'testHub.selectedPromptId';
const getTabIndexFromSearch = (search: string) => {
  const tab = new URLSearchParams(search).get('tab');
  if (tab === 'twilio') return 1;
  return 0;
};

export function TestHub() {
  const location = useLocation();
  const navigate = useNavigate();
  const { data: prompts = [], isLoading: loadingPrompts } = usePromptsQuery();
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const activeTabIndex = useMemo(() => getTabIndexFromSearch(location.search), [location.search]);
  const rawTabParam = useMemo(() => new URLSearchParams(location.search).get('tab'), [location.search]);

  const selectedPrompt = useMemo<PromptTemplate | undefined>(() => {
    if (!prompts.length) {
      return undefined;
    }
    return prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0];
  }, [prompts, selectedPromptId]);

  useEffect(() => {
    if (!prompts.length) return;

    let nextSelectedId = selectedPromptId;
    const hasSelected = nextSelectedId && prompts.some((prompt) => prompt.id === nextSelectedId);

    if (!hasSelected) {
      if (typeof window !== 'undefined') {
        try {
          const stored = window.localStorage.getItem(PROMPT_STORAGE_KEY);
          if (stored && prompts.some((prompt) => prompt.id === stored)) {
            nextSelectedId = stored;
          }
        } catch (error) {
          console.warn('读取 Prompt 选择缓存失败', error);
        }
      }

      if (!nextSelectedId || !prompts.some((prompt) => prompt.id === nextSelectedId)) {
        nextSelectedId = prompts[0]?.id ?? null;
      }
    }

    if (nextSelectedId !== selectedPromptId) {
      setSelectedPromptId(nextSelectedId);
      return;
    }

    if (!nextSelectedId || typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(PROMPT_STORAGE_KEY, nextSelectedId);
    } catch (error) {
      console.warn('保存 Prompt 选择缓存失败', error);
    }
  }, [prompts, selectedPromptId]);

  return (
    <section className="page-section">
      <PageTitle>实时调试实验室</PageTitle>
      <PageSubtitle>在单一界面体验 WebSocket 以及 Twilio WebCall 等链路，方便比对。</PageSubtitle>
      <Grid condensed fullWidth>
        <Column sm={4} md={8} lg={12}>
          <Tile className="prompt-selector">
            {loadingPrompts ? (
              <DropdownSkeleton />
            ) : (
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
            )}
          </Tile>
        </Column>
        <Column sm={4} md={8} lg={12}>
          <Tabs
            className="test-tabs"
            selectedIndex={activeTabIndex}
            onChange={({ selectedIndex }) => {
              const nextIndex = selectedIndex ?? 0;
              const nextTab = nextIndex === 1 ? 'twilio' : 'websocket';
              if (rawTabParam !== nextTab) {
                const params = new URLSearchParams(location.search);
                params.set('tab', nextTab);
                navigate({ pathname: '/test', search: `?${params.toString()}` });
              }
            }}
          >
            <TabList aria-label="测试架构选择">
              <Tab>WebSocket</Tab>
              <Tab>Twilio WebCall</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                {activeTabIndex === 0 ? <WebSocketConsole prompt={selectedPrompt} /> : null}
              </TabPanel>
              <TabPanel>
                {activeTabIndex === 1 ? <TwilioWebCallPanel prompt={selectedPrompt} /> : null}
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>
      </Grid>
    </section>
  );
}
