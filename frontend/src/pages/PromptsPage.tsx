import { Button, Column, Grid, Tag, Tile } from '@carbon/react';
import { useAppState } from '../state/AppStateContext';

export function PromptsPage() {
  const { prompts } = useAppState();

  return (
    <section className="page-section">
      <h1 className="page-title">Prompt 管理</h1>
      <p className="page-subtitle">编辑、版本对比、灰度发布智能体 Prompt 的公共入口。</p>
      <Grid condensed fullWidth>
        {prompts.map((prompt) => (
          <Column sm={4} md={4} lg={4} key={prompt.id}>
            <Tile className="prompt-tile">
              <h3>{prompt.name}</h3>
              <p className="prompt-body">{prompt.systemPrompt}</p>
              <Tag type="green">
                {prompt.version} · 更新于 {new Date(prompt.updatedAt).toLocaleDateString()}
              </Tag>
              <div className="prompt-actions">
                <Button kind="ghost" size="sm">
                  编辑配置
                </Button>
              </div>
            </Tile>
          </Column>
        ))}
      </Grid>
    </section>
  );
}
