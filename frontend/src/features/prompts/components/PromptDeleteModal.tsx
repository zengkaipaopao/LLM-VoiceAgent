import { useEffect, useState } from 'react';
import { Button, ComposedModal, ModalBody, ModalFooter, ModalHeader, TextInput } from '@carbon/react';

import { PromptTemplate } from '../../../types';
import styles from './PromptDeleteModal.module.css';

type PromptDeleteModalProps = {
  prompt: PromptTemplate | null;
  open: boolean;
  requiredPassword?: string;
  onCancel: () => void;
  onConfirm: (prompt: PromptTemplate) => Promise<void>;
};

export function PromptDeleteModal({
  prompt,
  open,
  onCancel,
  onConfirm,
  requiredPassword = 'admin',
}: PromptDeleteModalProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setPassword('');
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  if (!open || !prompt) {
    return null;
  }

  const handleConfirm = async () => {
    if (password !== requiredPassword) {
      setError('管理密码错误');
      return;
    }
    try {
      setSubmitting(true);
      await onConfirm(prompt);
      onCancel();
    } catch (error_) {
      console.error('删除 Prompt 失败', error_);
      setError('删除失败，请稍后再试。');
      setSubmitting(false);
    }
  };

  return (
    <ComposedModal open onClose={onCancel} size="sm">
      <ModalHeader title="确认删除 Prompt" closeButtonLabelText="关闭" />
      <ModalBody>
        <p className={styles.helper}>请输入管理密码以删除「{prompt.name}」。该操作不可恢复。</p>
        <TextInput
          id="prompt-delete-password"
          labelText="管理密码"
          type="password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            if (error) setError(null);
          }}
        />
        {error && <p className={styles.error}>{error}</p>}
      </ModalBody>
      <ModalFooter>
        <Button kind="secondary" onClick={onCancel} disabled={submitting}>
          取消
        </Button>
        <Button kind="danger" onClick={handleConfirm} disabled={submitting || !password.trim()}>
          {submitting ? '删除中...' : '确认删除'}
        </Button>
      </ModalFooter>
    </ComposedModal>
  );
}
