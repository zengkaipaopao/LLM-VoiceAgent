import { Button, InlineLoading, Select, SelectItem, TextInput } from '@carbon/react';

import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import type { PromptTemplate } from '../../../../types/shared';
import type { GeminiVoiceCatalog } from '../../../../api/geminiVoices';
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
  twilioMediaStreamVoiceOverride: string;
  setTwilioMediaStreamVoiceOverride: (value: string) => void;
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
  twilioMediaStreamVoiceOverride,
  setTwilioMediaStreamVoiceOverride,
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
  const isOfficialCaRoute = twilioGateway.transportMode === 'official_conversational_agents';

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
            (twilioGateway.loadingCapability ? (
              <InlineLoading description="加载配置中..." />
            ) : (
              <Button
                kind="ghost"
                size="sm"
                disabled={configLocked}
                onClick={() => {
                  void twilioGateway.refreshCapability();
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
              {isOfficialCaRoute ? (
                <>
                  <TextInput
                    id="twilio-official-ca-source"
                    labelText="Agent 配置来源"
                    value="Google CX Agent Studio / CES Deployment"
                    readOnly
                    helperText="电话侧对话逻辑、开场话术、模型与工具能力都由 Google 官方 Conversational Agents 配置管理。"
                  />
                  <TextInput
                    id="twilio-official-ca-mode"
                    labelText="当前电话路由"
                    value="official_conversational_agents"
                    readOnly
                    helperText="旧的 Media Streams -> Gemini Live 自建桥接已从主测试入口移除。当前页面固定走官方 CA 链路。"
                  />
                </>
              ) : (
                <>
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
                    labelText="当前生效 Gemini 音色"
                    value={effectiveVoice || ''}
                    readOnly
                    helperText={
                      isPromptVoiceConfigured
                        ? `当前 Prompt（${selectedPrompt?.code}）已提供 Gemini 音色；你也可以在下方手动覆盖。`
                        : '当前 Prompt 未设置 Gemini 音色，将使用下方覆盖值或后端默认音色。'
                    }
                  />

                  <Select
                    id="twilio-media-stream-voice"
                    labelText="Gemini 音色（可选）"
                    value={twilioMediaStreamVoiceOverride}
                    onChange={(event) => setTwilioMediaStreamVoiceOverride(event.target.value)}
                    helperText="电话音频会直接桥接到 Gemini Live。留空则优先跟随 Prompt 的 voice_id，否则使用后端默认音色。"
                    disabled={twilioSessionActive || loadingGeminiVoices}
                  >
                    <SelectItem
                      value=""
                      text={loadingGeminiVoices ? '正在加载 Gemini 音色...' : '自动（Prompt/默认）'}
                    />
                    {geminiVoiceCatalog.voices.map((voice) => (
                      <SelectItem key={voice} value={voice} text={voice} />
                    ))}
                  </Select>

                  <TextInput
                    id="twilio-media-stream-voice-override"
                    labelText="Gemini 音色（可手动输入）"
                    value={twilioMediaStreamVoiceOverride}
                    onChange={(event) => setTwilioMediaStreamVoiceOverride(event.target.value)}
                    helperText="这里可以直接输入 Gemini Live 预置音色名；留空则继续使用 Prompt 的 voice_id 或后端默认音色。"
                    disabled={twilioSessionActive}
                    placeholder={geminiVoiceCatalog.defaultVoice || 'Aoede'}
                  />
                </>
              )}

              <TextInput
                id="twilio-transport"
                labelText="当前接入方式"
                value={
                  isOfficialCaRoute
                    ? '官方 Conversational Agents（Google CX Agent Studio + Twilio）'
                    : 'Twilio Media Streams -> Gemini Live 音频双向桥接'
                }
                readOnly
                helperText={
                  isOfficialCaRoute
                    ? 'Twilio 负责电话接入，Google 官方 Conversational Agents 负责会话编排与语音能力。'
                    : 'Twilio 只负责电话接入与音频转发，Gemini Live 负责实时听说与回合控制。'
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
                    ? '已锁定为后端 TWILIO_PHONE_NUMBER。页面内“开始语音对话”会由浏览器先外呼到这个 Twilio 号码。'
                    : '请输入可拨打号码，例如 +8150xxxxxxx。浏览器 Twilio 测试会先拨到这里，再进入电话网关链路。'
                }
              />
              <TextInput
                id="twilio-inbound-number"
                labelText="已配置入站号码（Twilio）"
                value={twilioGateway.capability.configuredPhoneNumber || '-'}
                readOnly
                helperText={
                  isOfficialCaRoute
                    ? '真实手机直接拨打这个号码，也会走同一条官方 CA 电话链路。'
                    : '真实手机直接拨打这个号码，也会走同一条 Twilio Media Streams 电话链路。'
                }
              />
            </div>
            {!isOfficialCaRoute ? (
              <p className={styles.description}>
                Gemini 音色目录来源：{geminiVoiceCatalog.source}（共 {geminiVoiceCatalog.voices.length} 项）
              </p>
            ) : null}
          </>
        )}
      </section>

      <section className={styles.sectionBlock}>
        <h4 className="cds--heading-03">连接控制</h4>
        <p className={styles.description}>
          {routeMode === 'direct'
            ? '先建立浏览器直连会话，再开启麦克风。浏览器仅负责采音与播放期抑制，实际 turn 判定交给 Gemini Live。'
            : isOfficialCaRoute
              ? '页面内可按“准备下一通入呼”→ 真实手机拨打 Twilio 号码，或按 Token → 设备注册 → 开始语音对话 走浏览器外呼。两者都会进入同一条官方 Conversational Agents 电话链路。'
              : '页面内可按“准备下一通入呼”→ 真实手机拨打 Twilio 号码，或按 Token → 设备注册 → 开始语音对话 走浏览器外呼。两者都会进入同一条 Media Streams 电话音频桥接链路。'}
        </p>
        {routeMode === 'twilio' ? (
          <p className={styles.description}>
            {isOfficialCaRoute
              ? '浏览器外呼仅用于回归电话网关链路，建议佩戴耳机；若要验证最接近真实电话的效果，请优先使用真实手机拨打上方 Twilio 号码。当前电话路径固定走 Google 官方 Conversational Agents / CX Agent Studio 部署。'
              : '浏览器外呼仅用于回归电话网关链路，建议佩戴耳机；若要验证最接近真实电话的效果，请优先使用真实手机拨打上方 Twilio 号码。Media Streams 模式下，Twilio 只做电话音频转发，实时语音能力交给 Gemini Live。'}
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
                  voiceName: effectiveVoice || undefined,
                })
              }
              disabled={!canDial}
            >
              开始语音对话
            </Button>
            <Button kind="danger" size="sm" onClick={twilioGateway.hangupCall} disabled={!canHangup}>
              挂断
            </Button>
            <Button
              kind="ghost"
              size="sm"
              onClick={twilioGateway.unregisterDevice}
              disabled={twilioGateway.dialerStatus === 'registering'}
            >
              注销设备
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
