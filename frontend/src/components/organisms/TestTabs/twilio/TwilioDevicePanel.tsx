import { Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { TwilioDeviceActionButtons } from './TwilioDeviceActionButtons';
import { TwilioTokenConfigFields } from './TwilioTokenConfigFields';
import styles from '../TwilioTabContent.module.scss';

interface TwilioDevicePanelProps {
  useEndpoint: boolean;
  setUseEndpoint: (value: boolean) => void;
  tokenEndpoint: string;
  setTokenEndpoint: (value: string) => void;
  accessToken: string;
  setAccessToken: (value: string) => void;
  tokenEndpointPlaceholder: string;
  isFetchingToken: boolean;
  isInitializing: boolean;
  fetchToken: () => Promise<void>;
  initializeDevice: () => Promise<void>;
  handleUnregister: () => Promise<void>;
  resetSession: () => void;
}

export function TwilioDevicePanel({
  useEndpoint,
  setUseEndpoint,
  tokenEndpoint,
  setTokenEndpoint,
  accessToken,
  setAccessToken,
  tokenEndpointPlaceholder,
  isFetchingToken,
  isInitializing,
  fetchToken,
  initializeDevice,
  handleUnregister,
  resetSession,
}: TwilioDevicePanelProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.panelTile}>
      <h4 className="cds--heading-01">{t('pages:test.twilio.sections.device', 'Device 与 Token')}</h4>
      <p className={styles.description}>
        {t(
          'pages:test.twilio.sections.deviceDescription',
          '支持从后端拉取 Token，也支持手动粘贴 Token 进行联调。'
        )}
      </p>

      <TwilioTokenConfigFields
        useEndpoint={useEndpoint}
        setUseEndpoint={setUseEndpoint}
        tokenEndpoint={tokenEndpoint}
        setTokenEndpoint={setTokenEndpoint}
        accessToken={accessToken}
        setAccessToken={setAccessToken}
        tokenEndpointPlaceholder={tokenEndpointPlaceholder}
      />

      <TwilioDeviceActionButtons
        useEndpoint={useEndpoint}
        isFetchingToken={isFetchingToken}
        isInitializing={isInitializing}
        fetchToken={fetchToken}
        initializeDevice={initializeDevice}
        handleUnregister={handleUnregister}
        resetSession={resetSession}
      />
    </Tile>
  );
}
