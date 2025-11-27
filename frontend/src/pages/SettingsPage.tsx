import { useState } from 'react';
import { Column, Grid, Tile, Toggle, UnorderedList, ListItem } from '@carbon/react';
import { useAppState } from '../state/AppStateContext';

export function SettingsPage() {
  const { agents } = useAppState();
  const [featureFlags, setFeatureFlags] = useState({
    callRecording: true,
    realtimeTranscription: false,
    betaPromptEditor: true,
  });

  const handleToggle = (flag: keyof typeof featureFlags) => (checked: boolean) => {
    setFeatureFlags((prev) => ({ ...prev, [flag]: checked }));
  };

  return (
    <section className="page-section">
      <h1 className="page-title">系统设置</h1>
      <p className="page-subtitle">配置语音渠道、LLM Provider 凭证以及实验性 Feature Flags。</p>
      <Grid condensed fullWidth>
        <Column sm={4} md={4} lg={6}>
          <Tile>
            <h3>智能体配置</h3>
            <UnorderedList className="settings-list">
              {agents.map((agent) => (
                <ListItem key={agent.id}>
                  {agent.name} · {agent.llmProvider} · voice={agent.voice} · temp={agent.temperature}
                </ListItem>
              ))}
            </UnorderedList>
          </Tile>
        </Column>
        <Column sm={4} md={4} lg={6}>
          <Tile>
            <h3>Feature Flags</h3>
            <Toggle
              id="flag-recording"
              size="sm"
              labelText="启用通话录音"
              toggled={featureFlags.callRecording}
              onToggle={handleToggle('callRecording')}
            />
            <Toggle
              id="flag-realtime"
              size="sm"
              labelText="实时转写（预览）"
              toggled={featureFlags.realtimeTranscription}
              onToggle={handleToggle('realtimeTranscription')}
            />
            <Toggle
              id="flag-prompt"
              size="sm"
              labelText="Prompt 编辑器 Beta"
              toggled={featureFlags.betaPromptEditor}
              onToggle={handleToggle('betaPromptEditor')}
            />
          </Tile>
        </Column>
      </Grid>
    </section>
  );
}
