import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Button,
  ComposedModal,
  Dropdown,
  ModalBody,
  ModalFooter,
  ModalHeader,
  TextArea,
  TextInput,
  Toggle,
} from '@carbon/react';

import { ModelInfo, PromptCapabilities, PromptFormValues, PromptTemplate, VoiceConfig } from '../../../types';
import styles from './PromptEditorModal.module.css';

const defaultVoiceConfig: VoiceConfig = {
  voice: 'alloy',
  speakingRate: 1,
  noiseSuppression: true,
};

const defaultCapabilities: PromptCapabilities = {
  appointmentLogging: false,
  ttsEnabled: true,
};

type PromptEditorModalProps = {
  open: boolean;
  mode: 'create' | 'edit';
  prompt: PromptTemplate | null;
  models: ModelInfo[];
  onClose: () => void;
  onSave: (values: PromptFormValues, promptId?: string) => Promise<void>;
};

const buildDraft = (
  prompt: PromptTemplate | null,
  models: ModelInfo[],
  mode: 'create' | 'edit',
): PromptFormValues => {
  const fallbackModelId = prompt?.modelId ?? models[0]?.id ?? '';
  return {
    name: prompt?.name ?? '',
    modelId: fallbackModelId,
    systemPrompt: prompt?.systemPrompt ?? '',
    capabilities: {
      ...defaultCapabilities,
      ...(prompt?.capabilities ?? {}),
    },
    version: prompt?.version ?? 'v1.0.0',
    voiceConfig: { ...defaultVoiceConfig, ...(prompt?.voiceConfig ?? {}) },
  };
};

export function PromptEditorModal({ open, mode, prompt, models, onClose, onSave }: PromptEditorModalProps) {
  const [draft, setDraft] = useState<PromptFormValues>(() => buildDraft(prompt, models, mode));
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDraft(buildDraft(prompt, models, mode));
      setSaving(false);
      setErrorMessage(null);
    }
  }, [mode, models, open, prompt]);

  const ttsEnabled = draft.capabilities?.ttsEnabled ?? true;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft.modelId) {
      setErrorMessage('请先选择一个原始模型。');
      return;
    }
    try {
      setSaving(true);
      setErrorMessage(null);
      await onSave(
        {
          ...draft,
          capabilities: draft.capabilities ?? defaultCapabilities,
        },
        prompt?.id,
      );
      onClose();
    } catch (error) {
      console.error('保存 Prompt 失败', error);
      setSaving(false);
      setErrorMessage('保存失败，请稍后再试。');
    }
  };

  if (!open) {
    return null;
  }

  const selectedModel = models.find((model) => model.id === draft.modelId) ?? null;
  const modalTitle = mode === 'edit' ? `编辑 ${prompt?.name ?? ''}` : '新增 Prompt';
  const modalLabel = mode === 'edit' ? prompt?.modelId ?? '' : '创建新的 Prompt';

  return (
    <ComposedModal open onClose={onClose} size="lg">
      <ModalHeader label={modalLabel} title={modalTitle} closeButtonLabelText="关闭" />
      <form onSubmit={handleSubmit}>
        <ModalBody className={styles.modalBody}>
          <div className={styles.sectionHeader}>
            <h4 className={styles.sectionTitle}>基础信息</h4>
            <p className={styles.sectionSubtitle}>选择原始模型并为该 Prompt 设定版本号，便于灰度发布与回滚。</p>
          </div>
          <TextInput
            id="modal-prompt-name"
            labelText="Prompt 名称"
            value={draft.name}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
          <Dropdown
            id="modal-prompt-model"
            titleText="原始模型"
            label="选择模型"
            items={models}
            itemToString={(item) => (item ? item.name ?? item.id : '')}
            selectedItem={selectedModel}
            onChange={({ selectedItem }) => setDraft({ ...draft, modelId: (selectedItem as ModelInfo).id })}
            disabled={!models.length}
            helperText={
              models.length ? undefined : '暂无可选模型，请先在页面上配置可用模型。'
            }
          />
          <TextInput
            id="modal-prompt-version"
            labelText="版本号"
            value={draft.version}
            onChange={(event) => setDraft({ ...draft, version: event.target.value })}
          />
          <div className={styles.sectionHeader}>
            <h4 className={styles.sectionTitle}>对话策略</h4>
            <p className={styles.sectionSubtitle}>系统 Prompt 控制总体行为与欢迎语、结束语、流程引导，请在此处写完整的提示文案。</p>
          </div>
          <TextArea
            id="modal-prompt-system"
            labelText="系统 Prompt"
            rows={8}
            value={draft.systemPrompt}
            onChange={(event) => setDraft({ ...draft, systemPrompt: event.target.value })}
          />
          <div className={styles.sectionHeader}>
            <h4 className={styles.sectionTitle}>功能配置</h4>
            <p className={styles.sectionSubtitle}>按业务需求开启特定工具，例如预约记录写入。</p>
          </div>
          <div className={styles.capabilityGrid}>
            <div
              className={`${styles.capabilityCard} ${
                draft.capabilities?.appointmentLogging ? styles.capabilityCardActive : ''
              }`}
            >
              <div className={styles.capabilityCopy}>
                <p className={styles.capabilityEyebrow}>预约记录</p>
                <h5>落盘预约摘要</h5>
                <p>自动调用后端摘要模型，将对话写入「预约记录」页面。</p>
              </div>
              <Toggle
                id="modal-enable-appointment"
                labelText="生成预约记录"
                labelA="关闭"
                labelB="开启"
                toggled={draft.capabilities?.appointmentLogging ?? false}
                onToggle={() =>
                  setDraft((prev) => ({
                    ...prev,
                    capabilities: {
                      ...defaultCapabilities,
                      ...(prev.capabilities ?? {}),
                      appointmentLogging: !(prev.capabilities?.appointmentLogging ?? false),
                    },
                  }))
                }
              />
            </div>
            <div
              className={`${styles.capabilityCard} ${
                ttsEnabled ? styles.capabilityCardActive : ''
              }`}
            >
              <div className={styles.capabilityCopy}>
                <p className={styles.capabilityEyebrow}>语音播报</p>
                <h5>TTS/声音配置</h5>
                <p>启用后，测试页面可切换 TTS 服务并试听机器人语音。</p>
              </div>
              <Toggle
                id="modal-enable-tts"
                labelText="语音播报 / TTS"
                labelA="关闭"
                labelB="开启"
                toggled={ttsEnabled}
                onToggle={() =>
                  setDraft((prev) => ({
                    ...prev,
                    capabilities: {
                      ...defaultCapabilities,
                      ...(prev.capabilities ?? {}),
                      ttsEnabled: !(prev.capabilities?.ttsEnabled ?? true),
                    },
                  }))
                }
              />
            </div>
          </div>
          {errorMessage && <p className={styles.errorMessage}>{errorMessage}</p>}
        </ModalBody>
        <ModalFooter>
          <Button kind="secondary" onClick={onClose}>
            取消
          </Button>
          <Button kind="primary" type="submit" disabled={saving || !draft.name.trim() || !draft.modelId}>
            {saving ? '保存中...' : mode === 'edit' ? '保存' : '创建'}
          </Button>
        </ModalFooter>
      </form>
    </ComposedModal>
  );
}
