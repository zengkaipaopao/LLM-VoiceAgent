import { Button, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import styles from '../TwilioTabContent.module.scss';

interface TwilioGuidePanelProps {
  onViewCalls: () => void;
}

export function TwilioGuidePanel({ onViewCalls }: TwilioGuidePanelProps) {
  const { t } = useTranslation(['pages']);

  return (
    <Tile className={styles.panelTile}>
      <h4 className="cds--heading-01">{t('pages:test.twilio.sections.guide', '集成检查清单')}</h4>
      <ul className={styles.checkList}>
        <li>{t('pages:test.twilio.guide.step1', 'Twilio Console 中创建 Voice TwiML App，并配置 Voice URL。')}</li>
        <li>
          {t(
            'pages:test.twilio.guide.step2',
            '后端提供 Access Token 接口（建议 GET /api/v1/twilio/token?identity=...）。'
          )}
        </li>
        <li>{t('pages:test.twilio.guide.step3', '来电/去电参数中附带 prompt_code，后端映射到当前 Prompt 模板。')}</li>
        <li>{t('pages:test.twilio.guide.step4', '联调完成后，在通话记录页核对 Call SID、状态与摘要是否一致。')}</li>
      </ul>
      <div className={styles.buttonGroup}>
        <Button kind="ghost" size="sm" onClick={onViewCalls}>
          {t('pages:test.unified.actions.viewCalls', '查看通话记录')}
        </Button>
      </div>
    </Tile>
  );
}
