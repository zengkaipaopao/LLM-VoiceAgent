import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Checkbox,
  ComposedModal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Search,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
} from '@carbon/react';

import { ModelInfo } from '../../../types';
import styles from './ModelManagerModal.module.css';

type UsageTagId = 'realtime' | 'tts' | 'text' | 'multimodal';

type UsageOption = {
  id: UsageTagId;
  label: string;
};

const usageOptions: UsageOption[] = [
  { id: 'realtime', label: 'Realtime 对话' },
  { id: 'tts', label: '文本转语音' },
  { id: 'multimodal', label: '多模态 / 视觉' },
  { id: 'text', label: '文本生成' },
];

const usageTagType: Record<UsageTagId, string> = {
  realtime: 'blue',
  tts: 'purple',
  multimodal: 'magenta',
  text: 'cool-gray',
};
const usageLabelMap: Record<UsageTagId, string> = usageOptions.reduce(
  (acc, option) => ({ ...acc, [option.id]: option.label }),
  {} as Record<UsageTagId, string>,
);

type ModelManagerModalProps = {
  open: boolean;
  models: ModelInfo[];
  allowedModels: string[];
  onSave: (ids: string[]) => Promise<void>;
  onClose: () => void;
};

const deriveUsageTags = (model: ModelInfo): UsageTagId[] => {
  const tags: UsageTagId[] = [];
  const id = model.id.toLowerCase();
  const name = (model.name ?? '').toLowerCase();
  const description = (model.description ?? '').toLowerCase();
  const haystack = `${id} ${name} ${description}`;

  if (/(realtime|rt|phone|webrtc|sip)/.test(haystack)) {
    tags.push('realtime');
  }
  if (/(tts|speech|text-to-speech)/.test(haystack)) {
    tags.push('tts');
  }
  if (/(vision|omni|audio|multimodal|gemini|flash)/.test(haystack)) {
    tags.push('multimodal');
  }
  if (!tags.length) {
    tags.push('text');
  } else if (!tags.includes('text') && /(chat|text|gpt)/.test(haystack)) {
    tags.push('text');
  }
  return Array.from(new Set(tags));
};

export function ModelManagerModal({ open, models, allowedModels, onSave, onClose }: ModelManagerModalProps) {
  const [pendingAllowed, setPendingAllowed] = useState<string[]>(allowedModels);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [providerFilters, setProviderFilters] = useState<string[]>([]);
  const [usageFilters, setUsageFilters] = useState<UsageTagId[]>(usageOptions.map((option) => option.id));
  const [saving, setSaving] = useState(false);

  const providerOptions = useMemo(() => Array.from(new Set(models.map((model) => model.provider))).sort(), [models]);

  useEffect(() => {
    if (open) {
      setPendingAllowed(allowedModels);
      setSearchKeyword('');
      setProviderFilters(providerOptions);
      setUsageFilters(usageOptions.map((option) => option.id));
      setSaving(false);
    }
  }, [allowedModels, open, providerOptions]);

  const filteredModels = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    return models.filter((model) => {
      const matchesKeyword = keyword
        ? `${model.name ?? model.id} ${model.id}`.toLowerCase().includes(keyword)
        : true;
      const matchesProvider = providerFilters.length ? providerFilters.includes(model.provider) : true;
      const usageTags = deriveUsageTags(model);
      const matchesUsage = usageFilters.length ? usageFilters.some((tag) => usageTags.includes(tag)) : true;
      return matchesKeyword && matchesProvider && matchesUsage;
    });
  }, [models, providerFilters, searchKeyword, usageFilters]);

  const providerFilterIndeterminate =
    providerFilters.length > 0 && providerFilters.length < providerOptions.length;
  const usageFilterIndeterminate =
    usageFilters.length > 0 && usageFilters.length < usageOptions.length;

  const toggleModelSelection = (modelId: string) => {
    setPendingAllowed((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId],
    );
  };

  const toggleProviderSelection = (provider: string) => {
    setProviderFilters((prev) =>
      prev.includes(provider) ? prev.filter((item) => item !== provider) : [...prev, provider],
    );
  };

  const toggleUsageSelection = (usage: UsageTagId) => {
    setUsageFilters((prev) => (prev.includes(usage) ? prev.filter((item) => item !== usage) : [...prev, usage]));
  };

  const selectFilteredModels = () => {
    setPendingAllowed((prev) => {
      const next = new Set(prev);
      filteredModels.forEach((model) => next.add(model.id));
      return Array.from(next);
    });
  };

  const clearFilteredModels = () => {
    const filteredIds = new Set(filteredModels.map((model) => model.id));
    setPendingAllowed((prev) => prev.filter((id) => !filteredIds.has(id)));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await onSave(pendingAllowed);
      onClose();
    } catch (error) {
      console.error('保存模型白名单失败', error);
      setSaving(false);
    }
  };

  if (!open) {
    return null;
  }

  return (
    <ComposedModal open onClose={onClose} size="lg">
      <ModalHeader title="模型管理" closeButtonLabelText="关闭" />
      <ModalBody className={styles.modalBody}>
        {models.length === 0 ? (
          <p className={styles.emptyState}>还未从 Provider 获取到模型列表，请检查后端配置。</p>
        ) : (
          <>
            <div className={styles.summary}>
              <div className={styles.card}>
                <p className={styles.cardLabel}>已授权模型</p>
                <p className={styles.cardValue}>{pendingAllowed.length}</p>
                <p className={styles.cardHint}>共 {models.length} 个 Provider 模型</p>
              </div>
              <div className={styles.card}>
                <p className={styles.cardLabel}>可用 Provider</p>
                <p className={styles.cardValue}>{providerOptions.length}</p>
                <p className={styles.cardHint}>
                  {providerFilterIndeterminate ? `已选 ${providerFilters.length} 个` : '全部 Provider 已被选中'}
                </p>
              </div>
              <div className={styles.card}>
                <p className={styles.cardLabel}>使用场景筛选</p>
                <p className={styles.cardValue}>{usageFilters.length}</p>
                <p className={styles.cardHint}>
                  {usageFilterIndeterminate
                    ? `已选 ${usageFilters.length} / ${usageOptions.length}`
                    : usageFilters.length === usageOptions.length
                      ? '全部场景已启用'
                      : '暂未选择场景'}
                </p>
              </div>
              <div className={styles.card}>
                <p className={styles.cardLabel}>当前列表</p>
                <p className={styles.cardValue}>{filteredModels.length}</p>
                <p className={styles.cardHint}>根据搜索 / Provider 筛选</p>
              </div>
            </div>
            <div className={styles.layout}>
              <aside className={styles.sidebar}>
                <div className={styles.toolbar}>
                  <div>
                    <p className={styles.meta}>可用模型筛选</p>
                    <p className={styles.metaSub}>搜索或按 Provider 筛选以三步内定位模型。</p>
                  </div>
                </div>
                <Search
                  id="model-manager-search"
                  size="sm"
                  labelText="搜索模型"
                  placeholder="输入名称或模型 ID"
                  value={searchKeyword}
                  onChange={(event) => setSearchKeyword(event.target.value)}
                />
                <div className={styles.filterHeader}>
                  <p>Provider 筛选</p>
                  <Button size="sm" kind="ghost" onClick={() => setProviderFilters(providerOptions)} type="button">
                    全部
                  </Button>
                </div>
                <div className={styles.filterList}>
                  {providerOptions.map((provider) => (
                    <Checkbox
                      key={`provider-${provider}`}
                      id={`provider-${provider}`}
                      labelText={provider}
                      checked={providerFilters.includes(provider)}
                      onChange={() => toggleProviderSelection(provider)}
                    />
                  ))}
                  {!providerOptions.length && <p className={styles.metaSub}>暂无 Provider 信息。</p>}
                </div>
                <div className={styles.actions}>
                  <Button size="sm" kind="ghost" type="button" onClick={selectFilteredModels}>
                    全选当前结果
                  </Button>
                  <Button size="sm" kind="ghost" type="button" onClick={clearFilteredModels}>
                    取消当前结果
                  </Button>
                </div>
                <div className={styles.filterHeader}>
                  <p>使用场景</p>
                  <div>
                    <Button
                      size="sm"
                      kind="ghost"
                      type="button"
                      onClick={() => setUsageFilters(usageOptions.map((option) => option.id))}
                    >
                      全部
                    </Button>
                    <Button
                      size="sm"
                      kind="ghost"
                      type="button"
                      onClick={() => setUsageFilters([])}
                      disabled={usageFilters.length === 0}
                    >
                      清空
                    </Button>
                  </div>
                </div>
                <div className={styles.filterList}>
                  {usageOptions.map((usage) => (
                    <Checkbox
                      key={`usage-${usage.id}`}
                      id={`usage-${usage.id}`}
                      labelText={usage.label}
                      checked={usageFilters.includes(usage.id)}
                      onChange={() => toggleUsageSelection(usage.id)}
                    />
                  ))}
                </div>
                <p className={styles.helper}>勾选的模型会在 Prompt 设置时出现，未勾选的不会展示给运营同学。</p>
              </aside>
              <div className={styles.tableWrapper}>
                <StructuredListWrapper className={styles.table}>
                  <StructuredListHead>
                    <StructuredListRow head>
                      <StructuredListCell head>选择</StructuredListCell>
                      <StructuredListCell head>模型名称</StructuredListCell>
                      <StructuredListCell head>Provider</StructuredListCell>
                      <StructuredListCell head>用途</StructuredListCell>
                      <StructuredListCell head>ID</StructuredListCell>
                    </StructuredListRow>
                  </StructuredListHead>
                  <StructuredListBody>
                    {filteredModels.map((model) => {
                      const usageTags = deriveUsageTags(model);
                      return (
                        <StructuredListRow key={`allowed-${model.id}`} className={styles.row}>
                          <StructuredListCell>
                            <Checkbox
                              id={`model-${model.id}`}
                              labelText=""
                              hideLabel
                              checked={pendingAllowed.includes(model.id)}
                              onChange={() => toggleModelSelection(model.id)}
                            />
                          </StructuredListCell>
                          <StructuredListCell>
                            <div className={styles.modelName}>
                              <span>{model.name ?? model.id}</span>
                              {pendingAllowed.includes(model.id) && <Tag type="green">已启用</Tag>}
                            </div>
                          </StructuredListCell>
                          <StructuredListCell>
                            <Tag type="cool-gray">{model.provider}</Tag>
                          </StructuredListCell>
                          <StructuredListCell>
                            <div className={styles.usageTags}>
                              {usageTags.map((tag) => (
                                <Tag key={`${model.id}-${tag}`} type={usageTagType[tag]}>
                                  {usageLabelMap[tag]}
                                </Tag>
                              ))}
                            </div>
                          </StructuredListCell>
                          <StructuredListCell className={styles.idCell}>{model.id}</StructuredListCell>
                        </StructuredListRow>
                      );
                    })}
                    {!filteredModels.length && (
                      <StructuredListRow>
                        <StructuredListCell colSpan={5}>
                          <p className={styles.emptyState}>未找到匹配的模型，请调整筛选条件。</p>
                        </StructuredListCell>
                      </StructuredListRow>
                    )}
                  </StructuredListBody>
                </StructuredListWrapper>
              </div>
            </div>
          </>
        )}
      </ModalBody>
      <ModalFooter>
        <Button kind="secondary" onClick={onClose}>
          取消
        </Button>
        <Button kind="primary" onClick={handleSave} disabled={!models.length || saving}>
          {saving ? '保存中...' : '保存'}
        </Button>
      </ModalFooter>
    </ComposedModal>
  );
}
