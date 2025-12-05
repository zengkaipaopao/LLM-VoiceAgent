import { useCallback, useMemo, useState } from 'react';
import {
  Button,
  Column,
  Grid,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
  Tile,
} from '@carbon/react';

import { PromptEditorModal } from '../features/prompts/components/PromptEditorModal';
import { ModelManagerModal } from '../features/prompts/components/ModelManagerModal';
import { useAppState } from '../state/AppStateContext';
import { ModelInfo, PromptTemplate } from '../types';
import styles from './PromptsPage.module.css';

export function PromptsPage() {
  const { prompts, models, allowedModels, updatePromptTemplate, updateAllowedModels } = useAppState();
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [modelManagerOpen, setModelManagerOpen] = useState(false);

  const allowedSet = useMemo(() => new Set(allowedModels), [allowedModels]);
  const allowedModelItems = useMemo<ModelInfo[]>(() => models.filter((model) => allowedSet.has(model.id)), [allowedSet, models]);

  const openModelManager = () => setModelManagerOpen(true);

  const handlePromptSave = useCallback(
    (id: string, payload: Partial<PromptTemplate>) => updatePromptTemplate(id, payload),
    [updatePromptTemplate],
  );

  const handleAllowedModelsSave = useCallback((ids: string[]) => updateAllowedModels(ids), [updateAllowedModels]);

  return (
    <section className="page-section">
      <h1 className="page-title">Prompt 管理</h1>
      <p className="page-subtitle">编辑、版本对比、灰度发布智能体 Prompt 的公共入口。</p>
      <Grid condensed fullWidth>
        <Column sm={4} md={8} lg={12}>
          <Tile>
            <div className={styles.promptHeader}>
              <div>
                <h3 className={styles.tileTitle}>模型 Prompt 列表</h3>
                <p className={styles.tileDescription}>统一查看与维护所有智能体的提示词、原始模型及更新时间。</p>
              </div>
              <div className={styles.promptHeaderActions}>
                <Tag type="teal">共 {prompts.length} 条</Tag>
                <Button size="sm" kind="secondary" onClick={openModelManager}>
                  模型管理
                </Button>
              </div>
            </div>
            <StructuredListWrapper className={styles.promptList}>
              <StructuredListHead>
                <StructuredListRow head>
                  <StructuredListCell head>序号</StructuredListCell>
                  <StructuredListCell head>模型名称</StructuredListCell>
                  <StructuredListCell head>原始模型</StructuredListCell>
                  <StructuredListCell head>最近更新时间</StructuredListCell>
                </StructuredListRow>
              </StructuredListHead>
              <StructuredListBody>
                {prompts.map((prompt, index) => (
                  <StructuredListRow
                    key={`row-${prompt.id}`}
                    tabIndex={0}
                    onClick={() => setEditingPrompt(prompt)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setEditingPrompt(prompt);
                      }
                    }}
                    className={styles.promptListRow}
                  >
                    <StructuredListCell>{index + 1}</StructuredListCell>
                    <StructuredListCell>{prompt.name}</StructuredListCell>
                    <StructuredListCell>{prompt.modelId}</StructuredListCell>
                    <StructuredListCell>{new Date(prompt.updatedAt).toLocaleString()}</StructuredListCell>
                  </StructuredListRow>
                ))}
              </StructuredListBody>
            </StructuredListWrapper>
          </Tile>
        </Column>
      </Grid>
      <PromptEditorModal
        prompt={editingPrompt}
        models={allowedModelItems}
        onClose={() => setEditingPrompt(null)}
        onSave={handlePromptSave}
      />
      <ModelManagerModal
        open={modelManagerOpen}
        models={models}
        allowedModels={allowedModels}
        onClose={() => setModelManagerOpen(false)}
        onSave={handleAllowedModelsSave}
      />
    </section>
  );
}
