import { Button } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { DeviceState } from '../../../../hooks/useTwilioWebCallConsole';
import styles from '../TwilioTabContent.module.scss';

interface TwilioCallActionsProps {
  deviceState: DeviceState;
  isDialing: boolean;
  isEnding: boolean;
  canHangup: boolean;
  canMute: boolean;
  isMuted: boolean;
  handleDial: () => Promise<void>;
  handleHangUp: () => void;
  handleToggleMute: () => void;
  clearLogs: () => void;
}

export function TwilioCallActions({
  deviceState,
  isDialing,
  isEnding,
  canHangup,
  canMute,
  isMuted,
  handleDial,
  handleHangUp,
  handleToggleMute,
  clearLogs,
}: TwilioCallActionsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.actions}>
      <Button
        kind="primary"
        size="sm"
        onClick={() => {
          void handleDial();
        }}
        disabled={isDialing || isEnding || deviceState !== 'registered'}
      >
        {t('pages:test.twilio.actions.dial', '开始拨号')}
      </Button>
      <Button kind="secondary" size="sm" onClick={handleHangUp} disabled={!canHangup || isEnding}>
        {t('pages:test.twilio.actions.hangup', '挂断')}
      </Button>
      <Button kind="tertiary" size="sm" onClick={handleToggleMute} disabled={!canMute}>
        {isMuted
          ? t('pages:test.twilio.actions.unmute', '取消静音')
          : t('pages:test.twilio.actions.mute', '静音')}
      </Button>
      <Button kind="ghost" size="sm" onClick={clearLogs}>
        {t('pages:test.twilio.actions.clearLogs', '清空日志')}
      </Button>
    </div>
  );
}
