import {
  Button,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
} from '@carbon/react';

import { PromptTemplate } from '../../../types';
import styles from './PromptTable.module.css';

type PromptTableProps = {
  prompts: PromptTemplate[];
  className?: string;
  onEdit: (prompt: PromptTemplate) => void;
  onDelete: (prompt: PromptTemplate) => void;
};

export function PromptTable({ prompts, className, onEdit, onDelete }: PromptTableProps) {
  return (
    <StructuredListWrapper className={className}>
      <StructuredListHead>
        <StructuredListRow head>
          <StructuredListCell head>序号</StructuredListCell>
          <StructuredListCell head>模型名称</StructuredListCell>
          <StructuredListCell head>原始模型</StructuredListCell>
          <StructuredListCell head>最近更新时间</StructuredListCell>
          <StructuredListCell head>操作</StructuredListCell>
        </StructuredListRow>
      </StructuredListHead>
      <StructuredListBody>
        {prompts.map((prompt, index) => (
          <StructuredListRow key={`prompt-row-${prompt.id}`} className={styles.tableRow}>
            <StructuredListCell>{index + 1}</StructuredListCell>
            <StructuredListCell>{prompt.name}</StructuredListCell>
            <StructuredListCell>{prompt.modelId}</StructuredListCell>
            <StructuredListCell>{new Date(prompt.updatedAt).toLocaleString()}</StructuredListCell>
            <StructuredListCell>
              <div className={styles.actions}>
                <Button kind="ghost" size="sm" type="button" onClick={() => onEdit(prompt)}>
                  编辑
                </Button>
                <Button kind="danger--ghost" size="sm" type="button" onClick={() => onDelete(prompt)}>
                  删除
                </Button>
              </div>
            </StructuredListCell>
          </StructuredListRow>
        ))}
      </StructuredListBody>
    </StructuredListWrapper>
  );
}
