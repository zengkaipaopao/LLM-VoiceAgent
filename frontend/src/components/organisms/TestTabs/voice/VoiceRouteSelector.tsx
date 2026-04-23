import { Select, SelectItem, Tag, Tile } from '@carbon/react';

import styles from '../TwilioTabContent.module.scss';
import type { VoiceRouteMode } from './types';

interface VoiceRouteSelectorProps {
  routeMode: VoiceRouteMode;
  isAnySessionActive: boolean;
  onChange: (mode: VoiceRouteMode) => void;
}

export function VoiceRouteSelector({ routeMode, isAnySessionActive, onChange }: VoiceRouteSelectorProps) {
  const isDirect = routeMode === 'direct';
  const isOfficialTwilio = routeMode === 'twilio_official';

  return (
    <Tile className={styles.routeTile}>
      <div className={styles.sectionHeader}>
        <h4 className="cds--heading-03">测试方式</h4>
        <p className={styles.description}>
          该页面只关注语音链路是否稳定可对话。Twilio 仅作为电话接入网关，不是业务主流程。
        </p>
      </div>
      <Select
        id="voice-route-mode"
        labelText="语音接入方式"
        value={routeMode}
        onChange={(event) => onChange(event.target.value as VoiceRouteMode)}
        disabled={isAnySessionActive}
      >
        <SelectItem value="direct" text="浏览器直连 Gemini（不经过 Twilio）" />
        <SelectItem value="twilio_official" text="通过电话网关（Twilio，官方 Conversational Agents）" />
        <SelectItem value="twilio_media_stream" text="通过电话网关（Twilio，自建 Media Streams + 后端主控）" />
      </Select>
      <div className={styles.badgeRow}>
        <Tag type="teal">连通性回归</Tag>
        <Tag type={isDirect ? 'green' : isOfficialTwilio ? 'blue' : 'purple'}>
          {isDirect ? '直连模式' : isOfficialTwilio ? '官方电话模式' : '自建电话模式'}
        </Tag>
      </div>
      {isAnySessionActive && <p className={styles.description}>会话进行中，接入方式已锁定。请先断开会话后再切换。</p>}
      <p className={styles.routeHint}>
        {isDirect
          ? '浏览器麦克风会直接送到 Gemini Live，最适合先做模型对话连通验证。'
          : isOfficialTwilio
            ? '通过 Google 官方 Conversational Agents + Twilio 电话网关进行端到端验证。可在页面内发起浏览器外呼，也可先在页面准备下一通入呼，再用真实手机拨打 Twilio 号码。'
            : '通过 Twilio Media Streams + 你自己的后端主控链路进行端到端验证。该模式会把电话原始音频桥接到 Gemini Live，适合验证薄传输层实现。'}
      </p>
    </Tile>
  );
}
