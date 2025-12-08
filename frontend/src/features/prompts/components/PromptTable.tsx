import type { ComponentProps } from 'react';
import {
  Button,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
  Tag,
} from '@carbon/react';

import { PromptCapabilities, PromptTemplate } from '../../../types';
import styles from './PromptTable.module.css';

type PromptTableProps = {
  prompts: PromptTemplate[];
  className?: string;
  onEdit: (prompt: PromptTemplate) => void;
  onDelete: (prompt: PromptTemplate) => void;
};

type TagType = ComponentProps<typeof Tag>['type'];

type CapabilityDescriptor = {
  key: keyof PromptCapabilities;
  label: string;
  type: TagType;
  helperText?: string;
};

const capabilityDescriptors: CapabilityDescriptor[] = [
  {
    key: 'appointmentLogging',
    label: '预约记录',
    type: 'teal',
    helperText: '会话结束后支持自动生成预约记录',
  },
];

const renderCapabilityTags = (capabilities?: PromptCapabilities) => {
  const activeTags = capabilityDescriptors.filter((descriptor) => capabilities?.[descriptor.key]);
  if (!activeTags.length) {
    return <span className={styles.emptyCaps}>--</span>;
  }
  return (
    <div className={styles.capabilityTags}>
      {activeTags.map((descriptor) => (
        <Tag
          key={descriptor.key}
          type={descriptor.type}
          size="sm"
          title={descriptor.helperText ?? descriptor.label}
        >
          {descriptor.label}
        </Tag>
      ))}
    </div>
  );
};

export function PromptTable({ prompts, className, onEdit, onDelete }: PromptTableProps) {
  return (
    <StructuredListWrapper className={className}>
      <StructuredListHead>
        <StructuredListRow head>
          <StructuredListCell head>序号</StructuredListCell>
          <StructuredListCell head>模型名称</StructuredListCell>
          <StructuredListCell head>原始模型</StructuredListCell>
          <StructuredListCell head>功能标签</StructuredListCell>
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
            <StructuredListCell>{renderCapabilityTags(prompt.capabilities)}</StructuredListCell>
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
