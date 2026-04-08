import { Button, InlineLoading, TextInput } from '@carbon/react';

import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import type { PromptTemplate } from '../../../../types/shared';
import styles from '../TwilioTabContent.module.scss';
import { PromptTemplateSelect } from './PromptTemplateSelect';
import type { VoiceRouteMode } from './types';

interface VoiceSessionSectionProps {
  clientIdentity: string;
  routeMode: VoiceRouteMode;
  configLocked: boolean;
  selectedPromptCode: string;
  selectedPrompt?: PromptTemplate;
  effectiveVoice: string;
  isPromptVoiceConfigured: boolean;
  directSessionActive: boolean;
  twilioSessionActive: boolean;
  canDirectConnect: boolean;
  canDirectDisconnect: boolean;
  canDirectToggleMic: boolean;
  canDial: boolean;
  canHangup: boolean;
  liveWebsocket: UseLiveWebSocketConsoleResult;
  twilioGateway: UseTwilioVoiceGatewayResult;
}

export function VoiceSessionSection({
  clientIdentity,
  routeMode,
  configLocked,
  selectedPromptCode,
  selectedPrompt,
  effectiveVoice,
  isPromptVoiceConfigured,
  directSessionActive,
  twilioSessionActive,
  canDirectConnect,
  canDirectDisconnect,
  canDirectToggleMic,
  canDial,
  canHangup,
  liveWebsocket,
  twilioGateway,
}: VoiceSessionSectionProps) {
  const directMicActive = liveWebsocket.micStatus === 'on' || liveWebsocket.micStatus === 'starting';

  return (
    <div className={styles.mainTile}>
      <section className={styles.sectionBlock}>
        <div className={styles.headerRow}>
          <div className={styles.sectionHeader}>
            <h4 className="cds--heading-03">会话配置</h4>
            <p className={styles.description}>
              先确定 Prompt、模型与音色，再进入连接控制。保持配置最少、路径清晰，便于排障。
            </p>
          </div>
          {routeMode === 'twilio' &&
            (twilioGateway.loadingCapability || twilioGateway.loadingVoices ? (
              <InlineLoading description="加载配置中..." />
            ) : (
              <Button
                kind="ghost"
                size="sm"
                disabled={configLocked}
                onClick={() => {
                  void twilioGateway.refreshCapability();
                  void twilioGateway.refreshVoiceCatalog({ forceRefresh: true });
                }}
              >
                刷新配置
              </Button>
            ))}
        </div>

        {configLocked && <p className={styles.description}>会话进行中，配置已锁定。请先断开当前会话后再修改配置。</p>}

        {routeMode === 'direct' ? (
          <div className={styles.formGrid}>
            <PromptTemplateSelect
              id="direct-prompt-select"
              labelText="Prompt 模板"
              value={selectedPromptCode}
              prompts={liveWebsocket.prompts}
              loading={liveWebsocket.loadingPrompts}
              disabled={directSessionActive}
              onChange={liveWebsocket.setSelectedPromptCode}
            />

            <TextInput
              id="direct-model"
              labelText="Gemini Live 模型"
              value={liveWebsocket.model}
              onChange={(event) => liveWebsocket.setModel(event.target.value)}
              helperText="建议使用 Live 模型，如 gemini-3.1-flash-live-preview。"
              disabled={directSessionActive}
            />

            <TextInput
              id="direct-voice"
              labelText="Gemini 音色（可选）"
              value={liveWebsocket.voice}
              onChange={(event) => liveWebsocket.setVoice(event.target.value)}
              placeholder="留空则由后端默认或 Prompt 决定"
              disabled={directSessionActive}
            />

            <TextInput id="direct-ws-endpoint" labelText="当前连接端点" value={liveWebsocket.displayWsUrl} readOnly />
          </div>
        ) : (
          <>
            <div className={styles.formGrid}>
              <PromptTemplateSelect
                id="twilio-prompt-select"
                labelText="Prompt 模板"
                value={selectedPromptCode}
                prompts={liveWebsocket.prompts}
                loading={liveWebsocket.loadingPrompts}
                disabled={twilioSessionActive}
                onChange={liveWebsocket.setSelectedPromptCode}
              />

              <TextInput
                id="twilio-effective-voice"
                labelText="当前生效音色"
                value={effectiveVoice || ''}
                readOnly
                helperText={
                  isPromptVoiceConfigured
                    ? `来自 Prompt voice_id（${selectedPrompt?.code}）。`
                    : '当前 Prompt 未设置 voice_id，使用系统默认音色。'
                }
              />

              <TextInput id="twilio-identity" labelText="Client Identity" value={clientIdentity} readOnly />
              <TextInput
                id="twilio-target-number"
                labelText="目标号码（E.164）"
                value={twilioGateway.targetNumber}
                onChange={(event) => twilioGateway.setTargetNumber(event.target.value)}
                readOnly={twilioGateway.targetNumberLocked || twilioSessionActive}
                helperText={
                  twilioGateway.targetNumberLocked
                    ? '已锁定为后端 TWILIO_PHONE_NUMBER。'
                    : '请输入可拨打号码，例如 +8150xxxxxxx。'
                }
              />
              <TextInput
                id="twilio-inbound-number"
                labelText="已配置入站号码（Twilio）"
                value={twilioGateway.capability.configuredPhoneNumber || '-'}
                readOnly
              />
            </div>
            <p className={styles.description}>音色目录来源：{twilioGateway.voiceCatalog.source}（共 {twilioGateway.voiceCatalog.voices.length} 项）</p>
          </>
        )}
      </section>

      <section className={styles.sectionBlock}>
        <h4 className="cds--heading-03">连接控制</h4>
        <p className={styles.description}>
          {routeMode === 'direct'
            ? '连接 WebSocket 后再开启麦克风，逐步验证收音、转写与回复。'
            : '按 Token → 设备注册 → 拨号 的顺序执行电话链路验证。'}
        </p>

        {routeMode === 'direct' ? (
          <div className={styles.actionRow}>
            <Button kind="primary" size="sm" onClick={liveWebsocket.connectSocket} disabled={!canDirectConnect}>
              连接语音会话
            </Button>
            <Button kind="danger--tertiary" size="sm" onClick={liveWebsocket.disconnectSocket} disabled={!canDirectDisconnect}>
              断开会话
            </Button>
            <Button
              kind={directMicActive ? 'danger--tertiary' : 'secondary'}
              size="sm"
              onClick={() => liveWebsocket.toggleMicrophone(!directMicActive)}
              disabled={!canDirectToggleMic}
            >
              {directMicActive ? '关闭麦克风' : '开启麦克风'}
            </Button>
            <Button kind="ghost" size="sm" onClick={liveWebsocket.clearConsole}>
              清空会话记录
            </Button>
          </div>
        ) : (
          <div className={styles.actionRow}>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.fetchToken()}
              disabled={
                twilioGateway.dialerStatus === 'fetching_token' ||
                twilioGateway.dialerStatus === 'registering' ||
                twilioSessionActive
              }
            >
              获取 Token
            </Button>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.registerDevice()}
              disabled={twilioGateway.dialerStatus === 'registering' || twilioSessionActive}
            >
              初始化设备
            </Button>
            <Button kind="primary" size="sm" onClick={() => void twilioGateway.startDial({ promptCode: selectedPromptCode })} disabled={!canDial}>
              开始语音对话
            </Button>
            <Button kind="danger--tertiary" size="sm" onClick={twilioGateway.hangupCall} disabled={!canHangup}>
              挂断
            </Button>
            <Button kind="ghost" size="sm" onClick={twilioGateway.unregisterDevice}>
              注销设备
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
