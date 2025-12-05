import { FormEvent, useState } from 'react';
import {
  Button,
  Column,
  ComposedModal,
  Grid,
  ModalBody,
  ModalFooter,
  ModalHeader,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
  TextArea,
  TextInput,
  Tile,
} from '@carbon/react';
import { useAppState } from '../state/AppStateContext';
import { PromptTemplate } from '../types';

export function PromptsPage() {
  const { prompts, updatePromptTemplate } = useAppState();
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [draft, setDraft] = useState<PromptTemplate | null>(null);

  const openEditor = (prompt: PromptTemplate) => {
    setEditingPrompt(prompt);
    setDraft({ ...prompt });
  };

  const closeEditor = () => {
    setEditingPrompt(null);
    setDraft(null);
  };

  const handleSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingPrompt || !draft) return;
    updatePromptTemplate(editingPrompt.id, {
      name: draft.name,
      modelId: draft.modelId,
      systemPrompt: draft.systemPrompt,
      version: draft.version,
    });
    closeEditor();
  };

  return (
    <section className="page-section">
      <h1 className="page-title">Prompt 管理</h1>
      <p className="page-subtitle">编辑、版本对比、灰度发布智能体 Prompt 的公共入口。</p>
      <Grid condensed fullWidth>
        <Column sm={4} md={8} lg={12}>
          <Tile>
            <div className="prompt-header">
              <h3>模型 Prompt 列表</h3>
              <Tag type="teal">共 {prompts.length} 条</Tag>
            </div>
            <StructuredListWrapper className="prompt-list">
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
                    onClick={() => openEditor(prompt)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openEditor(prompt);
                      }
                    }}
                    className="prompt-list__row"
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
      {editingPrompt && draft && (
        <ComposedModal open onClose={closeEditor} size="lg">
          <ModalHeader label={draft.modelId} title={`编辑 ${draft.name}`} closeButtonLabelText="关闭" />
          <form onSubmit={handleSave}>
            <ModalBody>
              <TextInput
                id="modal-prompt-name"
                labelText="Prompt 名称"
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
              <TextInput
                id="modal-prompt-model"
                labelText="模型 ID"
                value={draft.modelId}
                onChange={(event) => setDraft({ ...draft, modelId: event.target.value })}
              />
              <TextInput
                id="modal-prompt-version"
                labelText="版本号"
                value={draft.version}
                onChange={(event) => setDraft({ ...draft, version: event.target.value })}
              />
              <TextArea
                id="modal-prompt-system"
                labelText="系统 Prompt"
                rows={8}
                value={draft.systemPrompt}
                onChange={(event) => setDraft({ ...draft, systemPrompt: event.target.value })}
              />
            </ModalBody>
            <ModalFooter>
              <Button kind="secondary" onClick={closeEditor}>
                取消
              </Button>
              <Button kind="primary" type="submit">
                保存
              </Button>
            </ModalFooter>
          </form>
        </ComposedModal>
      )}
    </section>
  );
}
