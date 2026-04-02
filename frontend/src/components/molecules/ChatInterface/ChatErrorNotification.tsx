import { ActionableNotification } from '@carbon/react';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation(['common', 'pages']);

  if (!error) {
    return null;
  }

  return (
    <ActionableNotification
      kind="error"
      title={t('common:status.error')}
      subtitle={error}
      actionButtonLabel={t('pages:test.chat.actions.retry', 'Retry')}
      onActionButtonClick={() => {
        void onRetry();
      }}
      lowContrast
      hideCloseButton={false}
      onCloseButtonClick={onDismiss}
    />
  );
}
