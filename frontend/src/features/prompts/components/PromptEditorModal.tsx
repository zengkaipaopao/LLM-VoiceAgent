import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  Button,
  ComposedModal,
  Dropdown,
  ModalBody,
  ModalFooter,
  ModalHeader,
  NumberInput,
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

const voicePresets = [
  { id: 'alloy', label: 'Alloy · 中性女声' },
  { id: 'ash', label: 'Ash · 沉稳低音' },
  { id: 'ballad', label: 'Ballad · 朗诵语气' },
  { id: 'coral', label: 'Coral · 年轻女声' },
  { id: 'echo', label: 'Echo · 清爽中性' },
  { id: 'sage', label: 'Sage · 专业男声' },
  { id: 'shimmer', label: 'Shimmer · 友好问候' },
  { id: 'verse', label: 'Verse · 温柔陪伴' },
  { id: 'marin', label: 'Marin · 日文气质' },
  { id: 'cedar', label: 'Cedar · 磁性男声' },
];

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
    welcomeMessage: prompt?.welcomeMessage ?? '',
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

  const activeVoiceConfig = useMemo(
    () => ({
      ...defaultVoiceConfig,
      ...(draft.voiceConfig ?? {}),
    }),
    [draft.voiceConfig],
  );
  const ttsEnabled = draft.capabilities?.ttsEnabled ?? true;

  const handleVoiceConfigChange = (patch: Partial<VoiceConfig>) => {
    setDraft({
      ...draft,
      voiceConfig: {
        ...activeVoiceConfig,
        ...patch,
      },
    });
  };

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
          voiceConfig: activeVoiceConfig,
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
            <p className={styles.sectionSubtitle}>系统 Prompt 控制总体行为，欢迎语决定连接后第一句话。</p>
          </div>
          <TextArea
            id="modal-prompt-system"
            labelText="系统 Prompt"
            rows={8}
            value={draft.systemPrompt}
            onChange={(event) => setDraft({ ...draft, systemPrompt: event.target.value })}
          />
          <TextArea
            id="modal-prompt-welcome"
            labelText="欢迎语"
            helperText="会话连接成功后用于自动播报的第一句话，可引导用户进入正题。"
            rows={4}
            value={draft.welcomeMessage ?? ''}
            onChange={(event) => setDraft({ ...draft, welcomeMessage: event.target.value })}
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
          <div
            className={`${styles.voiceConfig} ${!ttsEnabled ? styles.voiceConfigDisabled : ''}`}
            aria-disabled={!ttsEnabled}
          >
            <div className={styles.voiceConfigHeader}>
              <p className={styles.voiceConfigEyebrow}>音频参数</p>
              <h4>声音与音频控制</h4>
              <p>
                {ttsEnabled
                  ? '选择声线、语速和降噪策略，保持各测试链路体验一致。'
                  : '当前已关闭语音播报，开启后才能调整声音参数。'}
              </p>
            </div>
            <div className={styles.voiceConfigGrid}>
              <Dropdown
                id="modal-voice-preset"
                titleText="声音类型"
                label="选择声线"
                items={voicePresets}
                selectedItem={voicePresets.find((option) => option.id === activeVoiceConfig.voice) ?? voicePresets[0]}
                itemToString={(item) => (item ? item.label : '')}
                onChange={({ selectedItem }) =>
                  handleVoiceConfigChange({ voice: (selectedItem as (typeof voicePresets)[number]).id })
                }
                disabled={!ttsEnabled}
              />
              <NumberInput
                id="modal-voice-rate"
                label="语速"
                helperText="0.5 = 慢速 · 1 = 正常 · 1.5 = 稍快"
                min={0.5}
                max={1.5}
                step={0.05}
                value={activeVoiceConfig.speakingRate ?? 1}
                onChange={(event, { value }) => {
                  const numeric = Number(value);
                  handleVoiceConfigChange({ speakingRate: Number.isNaN(numeric) ? 1 : numeric });
                }}
                disabled={!ttsEnabled}
              />
              <div className={styles.voiceConfigToggle}>
                <Toggle
                  id="modal-voice-noise"
                  labelText="降噪"
                  labelA="关闭"
                  labelB="开启"
                  toggled={activeVoiceConfig.noiseSuppression ?? true}
                  onToggle={(state) => handleVoiceConfigChange({ noiseSuppression: state })}
                  disabled={!ttsEnabled}
                />
                <p>开启后将优先启用麦克风噪声抑制，WebRTC 测试最为明显。</p>
              </div>
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
