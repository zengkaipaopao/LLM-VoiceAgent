import { Select, SelectItem, Tag, Tile } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import styles from '../TwilioTabContent.module.scss';
import type { VoiceRouteMode } from './types';

interface VoiceRouteSelectorProps {
  routeMode: VoiceRouteMode;
  isAnySessionActive: boolean;
  onChange: (mode: VoiceRouteMode) => void;
}

export function VoiceRouteSelector({ routeMode, isAnySessionActive, onChange }: VoiceRouteSelectorProps) {
  const { t } = useTranslation(['pages']);
  const isDirect = routeMode === 'direct';
  const isOfficialTwilio = routeMode === 'twilio_official';

  return (
    <Tile className={styles.routeTile}>
      <div className={styles.sectionHeader}>
        <h4 className="cds--heading-03">{t('pages:test.voiceLab.routeSelector.title', 'Test mode')}</h4>
        <p className={styles.description}>
          {t(
            'pages:test.voiceLab.routeSelector.description',
            'This page focuses only on whether the voice path is stable enough for conversation. Twilio is only used as the phone ingress gateway, not the business flow itself.'
          )}
        </p>
      </div>
      <Select
        id="voice-route-mode"
        labelText={t('pages:test.voiceLab.routeSelector.label', 'Voice route')}
        value={routeMode}
        onChange={(event) => onChange(event.target.value as VoiceRouteMode)}
        disabled={isAnySessionActive}
      >
        <SelectItem
          value="direct"
          text={t('pages:test.voiceLab.routeSelector.options.direct', 'Browser direct to Gemini (without Twilio)')}
        />
        <SelectItem
          value="twilio_official"
          text={t(
            'pages:test.voiceLab.routeSelector.options.twilioOfficial',
            'Phone gateway (Twilio, official Conversational Agents)'
          )}
        />
        <SelectItem
          value="twilio_media_stream"
          text={t(
            'pages:test.voiceLab.routeSelector.options.twilioMediaStream',
            'Phone gateway (Twilio, self-hosted Media Streams + backend controller)'
          )}
        />
      </Select>
      <div className={styles.badgeRow}>
        <Tag type="teal">{t('pages:test.voiceLab.routeSelector.badges.regression', 'Connectivity regression')}</Tag>
        <Tag type={isDirect ? 'green' : isOfficialTwilio ? 'blue' : 'purple'}>
          {isDirect
            ? t('pages:test.voiceLab.routeSelector.badges.direct', 'Direct mode')
            : isOfficialTwilio
              ? t('pages:test.voiceLab.routeSelector.badges.twilioOfficial', 'Official phone mode')
              : t('pages:test.voiceLab.routeSelector.badges.twilioMediaStream', 'Self-hosted phone mode')}
        </Tag>
      </div>
      {isAnySessionActive && (
        <p className={styles.description}>
          {t(
            'pages:test.voiceLab.routeSelector.sessionLocked',
            'A session is in progress, so the route is locked. Disconnect first before switching.'
          )}
        </p>
      )}
      <p className={styles.routeHint}>
        {isDirect
          ? t(
              'pages:test.voiceLab.routeSelector.hints.direct',
              'The browser microphone is sent directly to Gemini Live, which is the best way to validate model conversation connectivity first.'
            )
          : isOfficialTwilio
            ? t(
                'pages:test.voiceLab.routeSelector.hints.twilioOfficial',
                'Run end-to-end verification through Google official Conversational Agents plus the Twilio phone gateway. You can place a browser outbound call here, or prepare the next inbound call and then dial the Twilio number from a real phone.'
              )
            : t(
                'pages:test.voiceLab.routeSelector.hints.twilioMediaStream',
                'Run end-to-end verification through Twilio Media Streams plus your own backend controller. This mode bridges raw phone audio into Gemini Live and is suited to validating a thin transport implementation.'
              )}
      </p>
    </Tile>
  );
}
