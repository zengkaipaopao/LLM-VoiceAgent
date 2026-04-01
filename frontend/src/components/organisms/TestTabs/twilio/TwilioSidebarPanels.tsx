import { Stack } from '@carbon/react';

import { TwilioDevicePanel } from './TwilioDevicePanel';
import { TwilioGuidePanel } from './TwilioGuidePanel';

interface TwilioSidebarPanelsProps {
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
  onViewCalls: () => void;
}

export function TwilioSidebarPanels({
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
  onViewCalls,
}: TwilioSidebarPanelsProps) {
  return (
    <Stack gap={6}>
      <TwilioDevicePanel
        useEndpoint={useEndpoint}
        setUseEndpoint={setUseEndpoint}
        tokenEndpoint={tokenEndpoint}
        setTokenEndpoint={setTokenEndpoint}
        accessToken={accessToken}
        setAccessToken={setAccessToken}
        tokenEndpointPlaceholder={tokenEndpointPlaceholder}
        isFetchingToken={isFetchingToken}
        isInitializing={isInitializing}
        fetchToken={fetchToken}
        initializeDevice={initializeDevice}
        handleUnregister={handleUnregister}
        resetSession={resetSession}
      />

      <TwilioGuidePanel onViewCalls={onViewCalls} />
    </Stack>
  );
}
