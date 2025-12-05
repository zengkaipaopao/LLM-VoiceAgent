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

type ModelManagerModalProps = {
  open: boolean;
  models: ModelInfo[];
  allowedModels: string[];
  onSave: (ids: string[]) => Promise<void>;
  onClose: () => void;
};

export function ModelManagerModal({ open, models, allowedModels, onSave, onClose }: ModelManagerModalProps) {
  const [pendingAllowed, setPendingAllowed] = useState<string[]>(allowedModels);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [providerFilters, setProviderFilters] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const providerOptions = useMemo(() => Array.from(new Set(models.map((model) => model.provider))).sort(), [models]);

  useEffect(() => {
    if (open) {
      setPendingAllowed(allowedModels);
      setSearchKeyword('');
      setProviderFilters(providerOptions);
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
      return matchesKeyword && matchesProvider;
    });
  }, [models, providerFilters, searchKeyword]);

  const providerFilterIndeterminate =
    providerFilters.length > 0 && providerFilters.length < providerOptions.length;

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
                <div className={styles.providerFilterHeader}>
                  <p>Provider 筛选</p>
                  <Button size="sm" kind="ghost" onClick={() => setProviderFilters(providerOptions)} type="button">
                    全部
                  </Button>
                </div>
                <div className={styles.providerFilterList}>
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
                <p className={styles.helper}>勾选的模型会在 Prompt 设置时出现，未勾选的不会展示给运营同学。</p>
              </aside>
              <div className={styles.tableWrapper}>
                <StructuredListWrapper className={styles.table}>
                  <StructuredListHead>
                    <StructuredListRow head>
                      <StructuredListCell head>选择</StructuredListCell>
                      <StructuredListCell head>模型名称</StructuredListCell>
                      <StructuredListCell head>Provider</StructuredListCell>
                      <StructuredListCell head>ID</StructuredListCell>
                    </StructuredListRow>
                  </StructuredListHead>
                  <StructuredListBody>
                    {filteredModels.map((model) => (
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
                        <StructuredListCell className={styles.idCell}>{model.id}</StructuredListCell>
                      </StructuredListRow>
                    ))}
                    {!filteredModels.length && (
                      <StructuredListRow>
                        <StructuredListCell colSpan={4}>
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
