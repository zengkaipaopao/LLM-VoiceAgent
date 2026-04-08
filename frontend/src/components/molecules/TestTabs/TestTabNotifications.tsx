import { InlineNotification } from '@carbon/react';

interface TestTabNotificationsProps {
  error?: string | null;
  info?: string | null;
  warning?: string | null;
  errorTitle: string;
  successTitle: string;
  warningTitle?: string;
  onClearError?: () => void;
  onClearInfo?: () => void;
}

export function TestTabNotifications({
  error,
  info,
  warning,
  errorTitle,
  successTitle,
  warningTitle,
  onClearError,
  onClearInfo,
}: TestTabNotificationsProps) {
  if (!error && !info && !warning) {
    return null;
  }

  return (
    <>
      {warning && (
        <InlineNotification
          kind="warning"
          title={warningTitle || 'Configuration warning'}
          subtitle={warning}
          lowContrast
          hideCloseButton
        />
      )}

      {error && (
        <InlineNotification
          kind="error"
          title={errorTitle}
          subtitle={error}
          lowContrast
          onCloseButtonClick={onClearError}
        />
      )}

      {info && (
        <InlineNotification
          kind="success"
          title={successTitle}
          subtitle={info}
          lowContrast
          onCloseButtonClick={onClearInfo}
        />
      )}
    </>
  );
}
