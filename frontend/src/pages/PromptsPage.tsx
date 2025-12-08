import { useCallback, useMemo, useState } from 'react';
import { Button, Column, Grid, Tag, Tile } from '@carbon/react';

import { PromptEditorModal } from '../features/prompts/components/PromptEditorModal';
import { ModelManagerModal } from '../features/prompts/components/ModelManagerModal';
import { PromptTable } from '../features/prompts/components/PromptTable';
import { PromptDeleteModal } from '../features/prompts/components/PromptDeleteModal';
import { useAppState } from '../state/AppStateContext';
import { ModelInfo, PromptFormValues, PromptTemplate } from '../types';
import styles from './PromptsPage.module.css';

type EditorState = {
  mode: 'create' | 'edit';
  prompt: PromptTemplate | null;
} | null;

export function PromptsPage() {
  const {
    prompts,
    models,
    allowedModels,
    updatePromptTemplate,
    createPromptTemplate,
    deletePromptTemplate,
    updateAllowedModels,
    createCustomModel,
    deleteCustomModel,
  } = useAppState();
  const [editorState, setEditorState] = useState<EditorState>(null);
  const [modelManagerOpen, setModelManagerOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PromptTemplate | null>(null);

  const allowedSet = useMemo(() => new Set(allowedModels), [allowedModels]);
  const allowedModelItems = useMemo<ModelInfo[]>(
    () => models.filter((model) => allowedSet.has(model.id)),
    [allowedSet, models],
  );

  const openModelManager = () => setModelManagerOpen(true);
  const openCreatePrompt = () => setEditorState({ mode: 'create', prompt: null });
  const openEditPrompt = (prompt: PromptTemplate) => setEditorState({ mode: 'edit', prompt });
  const closeEditor = () => setEditorState(null);

  const handlePromptSave = useCallback(
    async (payload: PromptFormValues, promptId?: string) => {
      if (editorState?.mode === 'edit' && promptId) {
        await updatePromptTemplate(promptId, {
          name: payload.name,
          modelId: payload.modelId,
          systemPrompt: payload.systemPrompt,
          welcomeMessage: payload.welcomeMessage,
          voiceConfig: payload.voiceConfig,
          version: payload.version,
        });
      } else {
        await createPromptTemplate(payload);
      }
    },
    [createPromptTemplate, editorState?.mode, updatePromptTemplate],
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
                <Button size="sm" kind="primary" onClick={openCreatePrompt}>
                  新增 Prompt
                </Button>
                <Button size="sm" kind="secondary" onClick={openModelManager}>
                  模型管理
                </Button>
              </div>
            </div>
            <PromptTable
              prompts={prompts}
              className={styles.promptList}
              onEdit={openEditPrompt}
              onDelete={setDeleteTarget}
            />
          </Tile>
        </Column>
      </Grid>
      <PromptEditorModal
        open={Boolean(editorState)}
        mode={editorState?.mode ?? 'edit'}
        prompt={editorState?.prompt ?? null}
        models={allowedModelItems}
        onClose={closeEditor}
        onSave={handlePromptSave}
      />
      <ModelManagerModal
        open={modelManagerOpen}
        models={models}
        allowedModels={allowedModels}
        onClose={() => setModelManagerOpen(false)}
        onSave={handleAllowedModelsSave}
        onCreateModel={createCustomModel}
        onDeleteModel={deleteCustomModel}
      />
      <PromptDeleteModal
        prompt={deleteTarget}
        open={Boolean(deleteTarget)}
        requiredPassword="admin"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async (prompt) => {
          await deletePromptTemplate(prompt.id);
          setDeleteTarget(null);
        }}
      />
    </section>
  );
}
