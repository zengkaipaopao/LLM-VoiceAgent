import { Tag } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { CallState, DeviceState, TwilioStatusTagType } from '../../../../hooks/useTwilioWebCallConsole';
import styles from '../TwilioTabContent.module.scss';

interface TwilioStatusHeaderProps {
  deviceState: DeviceState;
  callState: CallState;
  deviceTagType: TwilioStatusTagType;
  callTagType: TwilioStatusTagType;
}

export function TwilioStatusHeader({
  deviceState,
  callState,
  deviceTagType,
  callTagType,
}: TwilioStatusHeaderProps) {
  const { t } = useTranslation(['pages']);

  return (
    <div className={styles.header}>
      <div>
        <h3 className="cds--heading-03">{t('pages:test.twilio.title', 'Twilio 拨号测试台')}</h3>
        <p className={styles.description}>
          {t(
            'pages:test.twilio.subtitle',
            '按 Token -> Device -> Register -> Dial 的顺序调试 WebCall，完整保留事件日志用于排障。'
          )}
        </p>
      </div>
      <div className={styles.statusTags}>
        <Tag type={deviceTagType}>{`Device: ${deviceState}`}</Tag>
        <Tag type={callTagType}>{`Call: ${callState}`}</Tag>
      </div>
    </div>
  );
}
