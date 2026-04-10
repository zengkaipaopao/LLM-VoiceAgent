import React, { useState, useEffect } from 'react';
import { SmartDataTable } from '../../../components/organisms/DataTable/SmartDataTable';
import { Button, Tag } from '@carbon/react';
import { Edit, TrashCan, Add } from '@carbon/icons-react';
import { useTranslation } from 'react-i18next';
import { fetchPrompts, deletePrompt } from '../../../api/prompts';
import { PromptTemplate } from '../../../types/shared';
import styles from './PromptList.module.scss';

interface PromptListProps {
  onEdit: (prompt: PromptTemplate) => void;
  onCreate: () => void;
}

export const PromptList: React.FC<PromptListProps> = ({ onEdit, onCreate }) => {
  const { t } = useTranslation('pages');
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const headers = [
    { key: 'name', header: t('prompts.list.headers.name') },
    { key: 'code', header: t('prompts.list.headers.code') },
    { key: 'twilioPhoneNumber', header: '电话号码' },
    { key: 'llmModel', header: t('prompts.list.headers.model') },
    { key: 'temperature', header: t('prompts.list.headers.temperature') },
    { key: 'updatedAt', header: t('prompts.list.headers.updatedAt') },
    { key: 'actions', header: t('prompts.list.headers.actions') },
  ];

  const loadPrompts = async () => {
    setLoading(true);
    try {
      const data = await fetchPrompts();
      setPrompts(data);
    } catch (err) {
      console.error('Failed to load prompts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, []);

  const handleDelete = async (id: string) => {
    if (confirm(t('prompts.list.actions.deleteConfirm'))) {
      await deletePrompt(id);
      loadPrompts();
    }
  };

  // Prepare rows for SmartDataTable
  const rows = prompts.map((p) => ({
    id: p.id,
    name: p.name,
    code: p.code,
    twilioPhoneNumber:
      (p.twilioInboundNumbers || []).length > 0
        ? (p.twilioInboundNumbers || []).join(', ')
        : p.isTwilioIncomingDefault
          ? '未匹配号码时回退'
          : '-',
    llmModel: `${p.llmProvider}/${p.llmModel}`,
    temperature: p.temperature,
    updatedAt: new Date(p.updatedAt).toLocaleDateString(),
    original: p, 
  }));

  const renderCell = (cellValue: any, cellKey: string, row: any) => {
      switch (cellKey) {
          case 'code':
              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <code>{cellValue}</code>
                  {row.original.isTwilioIncomingDefault ? (
                    <Tag type="green">Twilio 入呼默认</Tag>
                  ) : null}
                </div>
              );
          case 'twilioPhoneNumber':
              return cellValue === '-' || cellValue === '未匹配号码时回退' ? cellValue : <code>{cellValue}</code>;
          case 'llmModel':
              return <Tag type="blue">{cellValue}</Tag>;
          case 'actions':
              return (
                <div style={{ display: 'flex', gap: '8px' }}>
                    <Button
                        kind="ghost"
                        size="sm"
                        hasIconOnly
                        renderIcon={Edit}
                        iconDescription={t('prompts.list.actions.edit')}
                        onClick={() => onEdit(row.original)}
                    />
                    <Button
                        kind="ghost"
                        size="sm"
                        hasIconOnly
                        renderIcon={TrashCan}
                        iconDescription={t('prompts.list.actions.delete')}
                        onClick={() => handleDelete(row.id)}
                        className={styles.dangerButton}
                    />
                </div>
              );
          default:
              return cellValue;
      }
  };

  return (
    <SmartDataTable
        rows={rows}
        headers={headers}
        loading={loading}
        title={t('prompts.title')}
        description={t('prompts.subtitle')}
        renderCell={renderCell}
        toolbarActions={
            <Button renderIcon={Add} onClick={onCreate}>
                {t('prompts.list.actions.create')}
            </Button>
        }
    />
  );
};
