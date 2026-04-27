import { Button, InlineLoading, Select, SelectItem, TextInput } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import type { UseLiveWebSocketConsoleResult } from '../../../../hooks/useLiveWebSocketConsole';
import type { UseTwilioVoiceGatewayResult } from '../../../../hooks/testTabs/useTwilioVoiceGateway';
import type { GeminiVoiceCatalog } from '../../../../api/geminiVoices';
import styles from '../TwilioTabContent.module.scss';
import { PromptTemplateSelect } from './PromptTemplateSelect';
import type { VoiceRouteMode } from './types';

interface VoiceSessionSectionProps {
  clientIdentity: string;
  routeMode: VoiceRouteMode;
  configLocked: boolean;
  selectedPromptCode: string;
  effectiveVoice: string;
  selectedPromptModel: string;
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
  effectiveVoice,
  selectedPromptModel,
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
  const isTwilioMode = routeMode !== 'direct';
  const isOfficialTwilio = routeMode === 'twilio_official';
  const isMediaStreamTwilio = routeMode === 'twilio_media_stream';
  const { t } = useTranslation(['pages']);
  const geminiVoiceLoadingText = t('pages:test.voiceLab.session.voiceLoading', 'Loading Gemini voices...');
  const geminiVoiceAutoText = t('pages:test.voiceLab.session.voiceAuto', 'Auto (Prompt/default)');

  return (
    <div className={styles.mainTile}>
      <section className={styles.sectionBlock}>
        <div className={styles.headerRow}>
          <div className={styles.sectionHeader}>
            <h4 className="cds--heading-03">{t('pages:test.voiceLab.session.configTitle', 'Session configuration')}</h4>
            <p className={styles.description}>
              {t(
                'pages:test.voiceLab.session.configDescription',
                'Lock in the Prompt, model, and voice first, then move on to connection controls. Keep configuration minimal and the route clear for easier troubleshooting.'
              )}
            </p>
          </div>
          {isTwilioMode &&
            (twilioGateway.loadingCapability ? (
              <InlineLoading description={t('pages:test.voiceLab.session.loadingConfig', 'Loading configuration...')} />
            ) : (
              <Button
                kind="ghost"
                size="sm"
                disabled={configLocked}
                onClick={() => {
                  void twilioGateway.refreshCapability();
                }}
              >
                {t('pages:test.voiceLab.session.refreshConfig', 'Refresh configuration')}
              </Button>
            ))}
        </div>

        {configLocked && (
          <p className={styles.description}>
            {t(
              'pages:test.voiceLab.session.configLocked',
              'A session is active, so configuration is locked. Disconnect the current session before editing.'
            )}
          </p>
        )}

        {routeMode === 'direct' ? (
          <div className={styles.formGrid}>
            <PromptTemplateSelect
              id="direct-prompt-select"
              labelText={t('pages:test.voiceLab.session.promptLabel', 'Prompt template')}
              value={selectedPromptCode}
              prompts={liveWebsocket.prompts}
              loading={liveWebsocket.loadingPrompts}
              disabled={directSessionActive}
              onChange={liveWebsocket.setSelectedPromptCode}
            />

            <TextInput
              id="direct-model"
              labelText={t('pages:test.voiceLab.session.modelLabel', 'Gemini Live model')}
              value={liveWebsocket.model}
              onChange={(event) => liveWebsocket.setModel(event.target.value)}
              helperText={t(
                'pages:test.voiceLab.session.directModelHelper',
                'Follows the Prompt llm_model by default and can be manually overridden here. Voice tests must use a Gemini Live or Native Audio model.'
              )}
              disabled={directSessionActive}
            />

            <Select
              id="direct-voice"
              labelText={t('pages:test.voiceLab.session.voiceLabel', 'Gemini voice (optional)')}
              value={liveWebsocket.voice}
              onChange={(event) => liveWebsocket.setVoice(event.target.value)}
              helperText={t(
                'pages:test.voiceLab.session.directVoiceHelper',
                'Leave blank to prefer the Prompt default voice; otherwise the system default voice is used.'
              )}
              disabled={directSessionActive || loadingGeminiVoices}
            >
              <SelectItem value="" text={loadingGeminiVoices ? geminiVoiceLoadingText : geminiVoiceAutoText} />
              {geminiVoiceCatalog.voices.map((voice) => (
                <SelectItem key={voice} value={voice} text={voice} />
              ))}
            </Select>

            <TextInput
              id="direct-ws-endpoint"
              labelText={t('pages:test.voiceLab.session.currentAccessMode', 'Current access mode')}
              value={liveWebsocket.displayWsUrl}
              readOnly
            />
          </div>
        ) : (
          <>
            <div className={styles.formGrid}>
              {isOfficialTwilio ? (
                <>
                  <TextInput
                    id="twilio-official-ca-source"
                    labelText={t('pages:test.voiceLab.session.agentConfigSource', 'Agent configuration source')}
                    value={t('pages:test.voiceLab.session.agentConfigSourceValue', 'Google CX Agent Studio / CES Deployment')}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.agentConfigSourceHelper',
                      'Phone-side dialog logic, opening utterance, model selection, and tool capabilities are all managed in Google official Conversational Agents.'
                    )}
                  />
                  <TextInput
                    id="twilio-official-ca-mode"
                    labelText={t('pages:test.voiceLab.session.currentPhoneRoute', 'Current phone route')}
                    value={t(
                      'pages:test.voiceLab.session.officialPhoneRouteValue',
                      'official_conversational_agents'
                    )}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.officialPhoneRouteHelper',
                      'The Google-managed conversation layer owns turn detection, orchestration, and tool capabilities, while the backend only handles phone ingress and bridging.'
                    )}
                  />
                  <TextInput
                    id="twilio-transport"
                    labelText={t('pages:test.voiceLab.session.currentAccessMode', 'Current access mode')}
                    value={t(
                      'pages:test.voiceLab.transport.official',
                      'Official Conversational Agents (Google CX Agent Studio + Twilio)'
                    )}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.officialTransportHelper',
                      'Twilio handles phone ingress, while Google official Conversational Agents handle conversation orchestration and voice capabilities.'
                    )}
                  />
                </>
              ) : (
                <>
                  <PromptTemplateSelect
                    id="twilio-media-stream-prompt-select"
                    labelText={t('pages:test.voiceLab.session.promptLabel', 'Prompt template')}
                    value={selectedPromptCode}
                    prompts={liveWebsocket.prompts}
                    loading={liveWebsocket.loadingPrompts}
                    disabled={twilioSessionActive}
                    onChange={liveWebsocket.setSelectedPromptCode}
                  />
                  <TextInput
                    id="twilio-media-stream-model"
                    labelText={t('pages:test.voiceLab.session.modelLabel', 'Gemini Live model')}
                    value={selectedPromptModel || '-'}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.mediaStreamModelHelper',
                      'This mode directly uses the Gemini Live / Native Audio model resolved from the local Prompt configuration.'
                    )}
                  />
                  <Select
                    id="twilio-media-stream-voice"
                    labelText={t('pages:test.voiceLab.session.voiceLabel', 'Gemini voice (optional)')}
                    value={liveWebsocket.voice}
                    onChange={(event) => liveWebsocket.setVoice(event.target.value)}
                    helperText={t(
                      'pages:test.voiceLab.session.mediaStreamVoiceHelper',
                      'Leave blank to prefer the Prompt default voice. This value is used as the Gemini Live voice override for the self-hosted Twilio Media Streams bridge.'
                    )}
                    disabled={twilioSessionActive || loadingGeminiVoices}
                  >
                    <SelectItem value="" text={loadingGeminiVoices ? geminiVoiceLoadingText : geminiVoiceAutoText} />
                    {geminiVoiceCatalog.voices.map((voice) => (
                      <SelectItem key={voice} value={voice} text={voice} />
                    ))}
                  </Select>
                  <TextInput
                    id="twilio-media-stream-route"
                    labelText={t('pages:test.voiceLab.session.currentPhoneRoute', 'Current phone route')}
                    value={t('pages:test.voiceLab.session.mediaStreamPhoneRouteValue', 'media_stream_live')}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.mediaStreamPhoneRouteHelper',
                      'Self-hosted Twilio Media Streams plus backend-controlled route. The current bridge has been refactored around a thin transport principle: continuous transcoding and forwarding without locally slicing input turns.'
                    )}
                  />
                  <TextInput
                    id="twilio-media-stream-effective-voice"
                    labelText={t('pages:test.voiceLab.session.effectiveVoiceLabel', 'Effective Gemini voice')}
                    value={effectiveVoice || '-'}
                    readOnly
                    helperText={t(
                      'pages:test.voiceLab.session.effectiveVoiceHelper',
                      'Resolved in this order: manual override -> Prompt default voice -> system default voice.'
                    )}
                  />
                </>
              )}

              <TextInput
                id="twilio-identity"
                labelText={t('pages:test.voiceLab.session.clientIdentity', 'Client Identity')}
                value={clientIdentity}
                readOnly
              />
              <TextInput
                id="twilio-target-number"
                labelText={t('pages:test.voiceLab.session.targetNumberLabel', 'Target number (E.164)')}
                value={twilioGateway.targetNumber}
                onChange={(event) => twilioGateway.setTargetNumber(event.target.value)}
                readOnly={twilioGateway.targetNumberLocked || twilioSessionActive}
                helperText={
                  twilioGateway.targetNumberLocked
                    ? t(
                        'pages:test.voiceLab.session.targetNumberLockedHelper',
                        'Locked to the backend TWILIO_PHONE_NUMBER. "Start voice conversation" on this page will place a browser outbound call to this Twilio number first.'
                      )
                    : t(
                        'pages:test.voiceLab.session.targetNumberEditableHelper',
                        'Enter a dialable number, for example +8150xxxxxxx. The browser Twilio test will dial here first and then enter the phone gateway route.'
                      )
                }
              />
              <TextInput
                id="twilio-inbound-number"
                labelText={t('pages:test.voiceLab.session.inboundNumberLabel', 'Configured inbound number (Twilio)')}
                value={twilioGateway.capability.configuredPhoneNumber || '-'}
                readOnly
                helperText={
                  isOfficialTwilio
                    ? t(
                        'pages:test.voiceLab.session.inboundNumberOfficialHelper',
                        'Dialing this number from a real phone will also use the same official CA phone route.'
                      )
                    : t(
                        'pages:test.voiceLab.session.inboundNumberMediaHelper',
                        'Dialing this number from a real phone will also use the same self-hosted Media Streams phone bridge.'
                      )
                }
              />
            </div>
          </>
        )}
      </section>

      <section className={styles.sectionBlock}>
        <h4 className="cds--heading-03">{t('pages:test.voiceLab.session.controlsTitle', 'Connection controls')}</h4>
        <p className={styles.description}>
          {routeMode === 'direct'
            ? t(
                'pages:test.voiceLab.session.controlsDirectDescription',
                'Establish the browser direct session first, then enable the microphone. The browser only handles capture and playback-time suppression; actual turn detection is handled by Gemini Live.'
              )
            : isOfficialTwilio
              ? t(
                  'pages:test.voiceLab.session.controlsOfficialDescription',
                  'You can prepare the next inbound call here and then dial the Twilio number from a real phone, or go through Token -> device registration -> Start voice conversation for browser outbound. Both enter the same official Conversational Agents phone route.'
                )
              : t(
                  'pages:test.voiceLab.session.controlsMediaDescription',
                  'You can prepare the next inbound call here and then dial the Twilio number from a real phone, or go through Token -> device registration -> Start voice conversation for browser outbound. Both enter the same self-hosted Media Streams plus backend-controlled route.'
                )}
        </p>
        {isTwilioMode ? (
          <p className={styles.description}>
            {isOfficialTwilio
              ? t(
                  'pages:test.voiceLab.session.controlsOfficialNote',
                  'Browser outbound is only for regressing the phone gateway route, so a headset is recommended. To validate behavior closest to a real phone call, prefer dialing the Twilio number above from a real handset. The current phone path is fixed to the Google official Conversational Agents / CX Agent Studio deployment.'
                )
              : t(
                  'pages:test.voiceLab.session.controlsMediaNote',
                  'Browser outbound is only for regressing the phone gateway route, so a headset is recommended. To validate behavior closest to a real phone call, prefer dialing the Twilio number above from a real handset. The current phone path bridges Twilio Media Streams phone audio directly into Gemini Live.'
                )}
          </p>
        ) : null}

        {routeMode === 'direct' ? (
          <div className={styles.actionRow}>
            <Button kind="primary" size="sm" onClick={liveWebsocket.connectSocket} disabled={!canDirectConnect}>
              {t('pages:test.voiceLab.session.actions.connectVoiceSession', 'Connect voice session')}
            </Button>
            <Button kind="danger--tertiary" size="sm" onClick={liveWebsocket.disconnectSocket} disabled={!canDirectDisconnect}>
              {t('pages:test.voiceLab.session.actions.disconnectAndExtract', 'Disconnect and extract')}
            </Button>
            <Button
              kind={directMicActive ? 'danger--tertiary' : 'secondary'}
              size="sm"
              onClick={() => liveWebsocket.toggleMicrophone(!directMicActive)}
              disabled={!canDirectToggleMic}
            >
              {directMicActive
                ? t('pages:test.voiceLab.session.actions.stopMicrophone', 'Stop microphone')
                : t('pages:test.voiceLab.session.actions.startMicrophone', 'Start microphone')}
            </Button>
            <Button kind="ghost" size="sm" onClick={liveWebsocket.clearConsole}>
              {t('pages:test.voiceLab.session.actions.clearSession', 'Clear session')}
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
                  voiceName: isMediaStreamTwilio ? liveWebsocket.voice || undefined : undefined,
                })
              }
              disabled={twilioSessionActive}
            >
              {t('pages:test.voiceLab.session.actions.prepareInbound', 'Prepare next inbound call')}
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
              {t('pages:test.voiceLab.session.actions.fetchToken', 'Fetch token')}
            </Button>
            <Button
              kind="secondary"
              size="sm"
              onClick={() => void twilioGateway.registerDevice()}
              disabled={twilioGateway.dialerStatus === 'registering' || twilioSessionActive}
            >
              {t('pages:test.voiceLab.session.actions.initializeDevice', 'Initialize device')}
            </Button>
            <Button
              kind="primary"
              size="sm"
              onClick={() =>
                void twilioGateway.startDial({
                  promptCode: selectedPromptCode,
                  voiceName: isMediaStreamTwilio ? liveWebsocket.voice || undefined : undefined,
                })
              }
              disabled={!canDial}
            >
              {t('pages:test.voiceLab.session.actions.startVoiceConversation', 'Start voice conversation')}
            </Button>
            <Button kind="danger" size="sm" onClick={twilioGateway.hangupCall} disabled={!canHangup}>
              {t('pages:test.voiceLab.session.actions.hangup', 'Hang up')}
            </Button>
            <Button
              kind="ghost"
              size="sm"
              onClick={twilioGateway.unregisterDevice}
              disabled={twilioGateway.dialerStatus === 'registering'}
            >
              {t('pages:test.voiceLab.session.actions.unregisterDevice', 'Unregister device')}
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
