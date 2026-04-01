import { InlineNotification } from '@carbon/react';

interface TestTabNotificationsProps {
  error?: string | null;
  info?: string | null;
  errorTitle: string;
  successTitle: string;
  onClearError?: () => void;
  onClearInfo?: () => void;
}

export function TestTabNotifications({
  error,
  info,
  errorTitle,
  successTitle,
  onClearError,
  onClearInfo,
}: TestTabNotificationsProps) {
  if (!error && !info) {
    return null;
  }

  return (
    <>
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
