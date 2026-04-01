import { ActionableNotification } from '@carbon/react';

interface ChatErrorNotificationProps {
  error: string | null;
  onRetry: () => Promise<void>;
  onDismiss: () => void;
}

export function ChatErrorNotification({
  error,
  onRetry,
  onDismiss,
}: ChatErrorNotificationProps) {
  if (!error) {
    return null;
  }

  return (
    <ActionableNotification
      kind="error"
      title="错误"
      subtitle={error}
      actionButtonLabel="重试"
      onActionButtonClick={() => {
        void onRetry();
      }}
      lowContrast
      hideCloseButton={false}
      onCloseButtonClick={onDismiss}
    />
  );
}
