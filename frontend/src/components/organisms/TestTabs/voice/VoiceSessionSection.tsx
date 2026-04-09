import { Button, InlineLoading, Select, SelectItem, TextInput } from '@carbon/react';

import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import type { PromptTemplate } from '../../../../types/shared';
import type { GeminiVoiceCatalog } from '../../../../api/geminiVoices';
import styles from '../TwilioTabContent.module.scss';
import { PromptTemplateSelect } from './PromptTemplateSelect';
import type { VoiceRouteMode } from './types';
import type { TwilioTtsProvider } from '../../../../features/test-lab/voice/adapters/twilio/useTwilioVoiceGateway';

interface VoiceSessionSectionProps {
  clientIdentity: string;
  routeMode: VoiceRouteMode;
  configLocked: boolean;
  selectedPromptCode: string;
  selectedPrompt?: PromptTemplate;
  effectiveVoice: string;
  isPromptVoiceConfigured: boolean;
  twilioTtsProvider: TwilioTtsProvider;
  setTwilioTtsProvider: (value: TwilioTtsProvider | '') => void;
  twilioVoiceOptions: string[];
  twilioVoicePreset: string;
  twilioVoiceOverride: string;
  setTwilioVoiceOverride: (value: string) => void;
  promptVoiceSupportedByTwilio: boolean;
  geminiVoiceCatalog: GeminiVoiceCatalog;
  loadingGeminiVoices: boolean;
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
  twilioTtsProvider,
  setTwilioTtsProvider,
  twilioVoiceOptions,
  twilioVoicePreset,
  twilioVoiceOverride,
  setTwilioVoiceOverride,
  promptVoiceSupportedByTwilio,
  geminiVoiceCatalog,
  loadingGeminiVoices,
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
                  void twilioGateway.refreshVoiceCatalog({
                    forceRefresh: true,
                    provider: twilioTtsProvider,
                  });
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
              helperText="默认跟随 Prompt 的 llm_model，可在这里手动覆盖；语音测试必须使用 Gemini Live 或 Native Audio 模型。"
              disabled={directSessionActive}
            />

            <Select
              id="direct-voice"
              labelText="Gemini 音色（可选）"
              value={liveWebsocket.voice}
              onChange={(event) => liveWebsocket.setVoice(event.target.value)}
              helperText="留空则优先跟随 Prompt 的默认音色，否则使用系统默认音色。"
              disabled={directSessionActive || loadingGeminiVoices}
            >
              <SelectItem
                value=""
                text={loadingGeminiVoices ? '正在加载 Gemini 音色...' : '自动（Prompt/默认）'}
              />
              {geminiVoiceCatalog.voices.map((voice) => (
                <SelectItem key={voice} value={voice} text={voice} />
              ))}
            </Select>

            <TextInput id="direct-ws-endpoint" labelText="当前接入方式" value={liveWebsocket.displayWsUrl} readOnly />
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
                    ? `当前 Prompt 的 voice_id 已映射为 Twilio 官方支持音色（${selectedPrompt?.code} / ${twilioTtsProvider}）。`
                    : (selectedPrompt?.voiceId || '').trim()
                      ? `当前 Prompt 的 voice_id 不在当前 ${twilioTtsProvider} 官方支持列表中，已回退到该 provider 的默认音色。`
                      : `当前 Prompt 未设置 voice_id，使用 ${twilioTtsProvider} 的默认音色。`
                }
              />

              <Select
                id="twilio-tts-provider"
                labelText="电话语音层（Twilio 官方）"
                value={twilioTtsProvider}
                onChange={(event) => setTwilioTtsProvider(event.target.value as TwilioTtsProvider)}
                helperText="ConversationRelay 官方支持 Google、Amazon Polly 和 ElevenLabs。切换后，下方只显示该 provider 官方支持的 voice ID。"
                disabled={twilioSessionActive || twilioGateway.loadingVoices}
              >
                {twilioGateway.voiceCatalog.providers.map((provider) => (
                  <SelectItem key={provider} value={provider} text={provider} />
                ))}
              </Select>

              <Select
                id="twilio-voice-preset"
                labelText="从官方列表选择 Voice ID（可选）"
                value={twilioVoicePreset}
                onChange={(event) => setTwilioVoiceOverride(event.target.value)}
                helperText={
                  twilioTtsProvider === 'ElevenLabs' && twilioVoiceOptions.length <= 1
                    ? 'Twilio 官方文档当前公开的是该语言的默认 ElevenLabs voice。你也可以在下方直接输入官方 voice ID。'
                    : promptVoiceSupportedByTwilio
                      ? `留空则跟随 Prompt 在 ${twilioTtsProvider} 下的默认音色；也可以从这里快速选择官方 voice ID。`
                      : `留空则使用 ${twilioTtsProvider} 的官方默认音色；也可以在下方手动输入官方 voice ID。`
                }
                disabled={twilioSessionActive || twilioGateway.loadingVoices}
              >
                <SelectItem
                  value=""
                  text={twilioGateway.loadingVoices ? '正在加载 Twilio 官方音色...' : '自动（Prompt/provider 默认）'}
                />
                {twilioVoiceOptions.map((voice) => (
                  <SelectItem key={voice} value={voice} text={voice} />
                ))}
              </Select>

              <TextInput
                id="twilio-voice"
                labelText="电话音色 Voice ID（可手动输入）"
                value={twilioVoiceOverride}
                onChange={(event) => setTwilioVoiceOverride(event.target.value)}
                helperText={
                  twilioTtsProvider === 'ElevenLabs'
                    ? '这里可以直接输入 Twilio ConversationRelay 官方支持的 ElevenLabs voice ID；留空则继续使用 Prompt/provider 默认音色。'
                    : `这里可以直接输入 ${twilioTtsProvider} 在 Twilio 官方文档中的 voice ID；留空则继续使用 Prompt/provider 默认音色。`
                }
                disabled={twilioSessionActive}
                placeholder={
                  twilioGateway.voiceCatalog.defaultVoice ||
                  (twilioTtsProvider === 'Google'
                    ? 'ja-JP-Chirp3-HD-Aoede'
                    : twilioTtsProvider === 'Amazon'
                      ? 'Mizuki-Neural'
                      : 'NYC9WEgkq1u4jiqBseQ9')
                }
              />

              <TextInput
                id="twilio-transport"
                labelText="当前接入方式"
                value="Twilio ConversationRelay -> Gemini 文本流式生成"
                readOnly
                helperText="保持与浏览器直连分离：切到 Twilio 时只验证电话网关链路，Twilio 负责电话语音层，Gemini 负责文本对话生成。"
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
                    ? '已锁定为后端 TWILIO_PHONE_NUMBER。页面内“开始语音对话”会由浏览器先外呼到这个 Twilio 号码。'
                    : '请输入可拨打号码，例如 +8150xxxxxxx。浏览器 Twilio 测试会先拨到这里，再进入电话网关链路。'
                }
              />
              <TextInput
                id="twilio-inbound-number"
                labelText="已配置入站号码（Twilio）"
                value={twilioGateway.capability.configuredPhoneNumber || '-'}
                readOnly
                helperText="真实手机直接拨打这个号码，也会走同一条 Twilio ConversationRelay 电话链路。"
              />
            </div>
            <p className={styles.description}>
              音色目录来源：{twilioGateway.voiceCatalog.source}
              {twilioVoiceOptions.length === twilioGateway.voiceCatalog.voices.length
                ? `（共 ${twilioVoiceOptions.length} 项）`
                : `（官方目录 ${twilioGateway.voiceCatalog.voices.length} 项，含快捷项共 ${twilioVoiceOptions.length} 项）`}
            </p>
          </>
        )}
      </section>

      <section className={styles.sectionBlock}>
        <h4 className="cds--heading-03">连接控制</h4>
        <p className={styles.description}>
          {routeMode === 'direct'
            ? '先建立浏览器直连会话，再开启麦克风。浏览器仅负责采音与播放期抑制，实际 turn 判定交给 Gemini Live。'
            : '页面内可按“准备下一通入呼”→ 真实手机拨打 Twilio 号码，或按 Token → 设备注册 → 开始语音对话 走浏览器外呼。两者都会进入同一条 ConversationRelay 电话网关链路。'}
        </p>
        {routeMode === 'twilio' ? (
          <p className={styles.description}>
            浏览器外呼仅用于回归电话网关链路，建议佩戴耳机；若要验证最接近真实电话的效果，请优先使用真实手机拨打上方 Twilio 号码。ConversationRelay 会由 Twilio 负责 STT/TTS 与打断处理。
          </p>
        ) : null}

        {routeMode === 'direct' ? (
          <div className={styles.actionRow}>
            <Button kind="primary" size="sm" onClick={liveWebsocket.connectSocket} disabled={!canDirectConnect}>
              连接语音会话
            </Button>
            <Button kind="danger--tertiary" size="sm" onClick={liveWebsocket.disconnectSocket} disabled={!canDirectDisconnect}>
              断开并提取
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
              onClick={() =>
                void twilioGateway.prepareInboundCall({
                  promptCode: selectedPromptCode,
                  ttsProvider: twilioTtsProvider,
                  voiceName: effectiveVoice || undefined,
                })
              }
              disabled={twilioSessionActive}
            >
              准备下一通入呼
            </Button>
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
            <Button
              kind="primary"
              size="sm"
              onClick={() =>
                void twilioGateway.startDial({
                  promptCode: selectedPromptCode,
                  ttsProvider: twilioTtsProvider,
                  voiceName: effectiveVoice || undefined,
                })
              }
              disabled={!canDial}
            >
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
