import { Button } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import styles from '../TwilioTabContent.module.scss';

interface TwilioDeviceActionButtonsProps {
  useEndpoint: boolean;
  isFetchingToken: boolean;
  isInitializing: boolean;
  fetchToken: () => Promise<void>;
  initializeDevice: () => Promise<void>;
  handleUnregister: () => Promise<void>;
  resetSession: () => void;
}

export function TwilioDeviceActionButtons({
  useEndpoint,
  isFetchingToken,
  isInitializing,
  fetchToken,
  initializeDevice,
  handleUnregister,
  resetSession,
}: TwilioDeviceActionButtonsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.buttonGroup}>
      <Button
        kind="primary"
        size="sm"
        onClick={() => {
          void fetchToken();
        }}
        disabled={!useEndpoint || isFetchingToken}
      >
        {t('pages:test.twilio.actions.fetchToken', '获取 Token')}
      </Button>

      <Button
        kind="secondary"
        size="sm"
        onClick={() => {
          void initializeDevice();
        }}
        disabled={isInitializing}
      >
        {t('pages:test.twilio.actions.initDevice', '初始化 Device')}
      </Button>

      <Button
        kind="tertiary"
        size="sm"
        onClick={() => {
          void handleUnregister();
        }}
      >
        {t('pages:test.twilio.actions.unregister', '注销 Device')}
      </Button>

      <Button kind="ghost" size="sm" onClick={resetSession}>
        {t('pages:test.twilio.actions.reset', '重置会话')}
      </Button>
    </div>
  );
}
