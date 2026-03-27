import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Column,
  Grid,
  InlineLoading,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  Tag,
  TextArea,
  TextInput,
  Tile,
  Toggle,
} from '@carbon/react';
import { Call, Device } from '@twilio/voice-sdk';

import { API_BASE_URL } from '../../../api/http';
import { fetchPrompts } from '../../../api/prompts';
import { PromptTemplate } from '../../../types/shared';
import styles from './TwilioTabContent.module.scss';

type DeviceState = 'idle' | 'registering' | 'registered' | 'unregistered' | 'error';
type CallState = 'idle' | 'dialing' | 'ringing' | 'in_call' | 'ending' | 'ended' | 'error';
type LogLevel = 'info' | 'success' | 'warning' | 'error';

interface EventLog {
  id: string;
  time: Date;
  level: LogLevel;
  message: string;
}

function stringifyError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  try {
    return JSON.stringify(error);
  } catch {
    return 'Unknown error';
  }
}

function extractToken(payload: any): string | null {
  if (!payload) return null;
  return (
    payload?.token ||
    payload?.access_token ||
    payload?.accessToken ||
    payload?.data?.token ||
    payload?.data?.access_token ||
    payload?.data?.accessToken ||
    null
  );
}

export function TwilioTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);

  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [selectedPromptCode, setSelectedPromptCode] = useState('');

  const [identity, setIdentity] = useState('webcall-tester');
  const [toNumber, setToNumber] = useState('+819012345678');
  const [tokenEndpoint, setTokenEndpoint] = useState(`${API_BASE_URL}/twilio/token`);
  const [useEndpoint, setUseEndpoint] = useState(true);
  const [accessToken, setAccessToken] = useState('');

  const [deviceState, setDeviceState] = useState<DeviceState>('idle');
  const [callState, setCallState] = useState<CallState>('idle');
  const [callSid, setCallSid] = useState<string>('');
  const [isMuted, setIsMuted] = useState(false);

  const [logs, setLogs] = useState<EventLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [isFetchingToken, setIsFetchingToken] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isDialing, setIsDialing] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  const deviceRef = useRef<Device | null>(null);
  const callRef = useRef<Call | null>(null);

  const pushLog = useCallback((level: LogLevel, message: string) => {
    setLogs((prev) => {
      const next = [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          time: new Date(),
          level,
          message,
        },
      ];
      return next.slice(-120);
    });
  }, []);

  const clearAlerts = () => {
    setError(null);
    setInfo(null);
  };

  const resetSession = useCallback(() => {
    try {
      callRef.current?.disconnect();
    } catch {
      // noop
    }
    callRef.current = null;

    try {
      deviceRef.current?.destroy();
    } catch {
      // noop
    }
    deviceRef.current = null;

    setDeviceState('idle');
    setCallState('idle');
    setCallSid('');
    setIsMuted(false);
  }, []);

  useEffect(() => {
    const loadPrompts = async () => {
      try {
        const list = await fetchPrompts();
        setPrompts(list);
        if (list.length > 0) {
          const defaultPrompt = list.find((item) => item.code === 'base_appointment') || list[0];
          setSelectedPromptCode(defaultPrompt.code);
        }
      } catch (loadError) {
        pushLog('error', `Prompt list load failed: ${stringifyError(loadError)}`);
      } finally {
        setLoadingPrompts(false);
      }
    };

    loadPrompts();
  }, [pushLog]);

  useEffect(() => {
    return () => {
      resetSession();
    };
  }, [resetSession]);

  const fetchToken = useCallback(async () => {
    if (!useEndpoint) return;
    setIsFetchingToken(true);
    clearAlerts();
    try {
      const base = tokenEndpoint.trim() || `${API_BASE_URL}/twilio/token`;
      const connector = base.includes('?') ? '&' : '?';
      const url = `${base}${connector}identity=${encodeURIComponent(identity.trim() || 'webcall-tester')}`;
      const response = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        throw new Error(`Token endpoint returned ${response.status}`);
      }

      const payload = await response.json();
      const token = extractToken(payload);
      if (!token) {
        throw new Error('No token field found in endpoint response');
      }
      setAccessToken(token);
      setInfo(t('pages:test.twilio.info.tokenFetched', 'Twilio token fetched successfully.'));
      pushLog('success', 'Access token fetched from endpoint.');
    } catch (fetchError) {
      const message = stringifyError(fetchError);
      setError(message);
      pushLog('error', `Fetch token failed: ${message}`);
    } finally {
      setIsFetchingToken(false);
    }
  }, [identity, pushLog, t, tokenEndpoint, useEndpoint]);

  const bindCallEvents = useCallback(
    (call: Call) => {
      call.on('ringing', () => {
        setCallState('ringing');
        pushLog('info', 'Call is ringing.');
      });

      call.on('accept', () => {
        setCallState('in_call');
        setIsDialing(false);
        setCallSid(call.parameters?.CallSid || '');
        pushLog('success', 'Call connected.');
      });

      call.on('disconnect', () => {
        setCallState('ended');
        setIsDialing(false);
        setIsEnding(false);
        setIsMuted(false);
        setCallSid(call.parameters?.CallSid || '');
        callRef.current = null;
        pushLog('info', 'Call disconnected.');
      });

      call.on('cancel', () => {
        setCallState('ended');
        setIsDialing(false);
        setIsEnding(false);
        setIsMuted(false);
        callRef.current = null;
        pushLog('warning', 'Call canceled.');
      });

      call.on('reject', () => {
        setCallState('ended');
        setIsDialing(false);
        setIsEnding(false);
        setIsMuted(false);
        callRef.current = null;
        pushLog('warning', 'Call rejected.');
      });

      call.on('mute', (muted: boolean) => {
        setIsMuted(muted);
        pushLog('info', muted ? 'Microphone muted.' : 'Microphone unmuted.');
      });

      call.on('warning', (name: string) => {
        pushLog('warning', `Twilio warning: ${name}`);
      });

      call.on('warning-cleared', (name: string) => {
        pushLog('info', `Twilio warning cleared: ${name}`);
      });

      call.on('error', (callError: any) => {
        const message = stringifyError(callError);
        setCallState('error');
        setIsDialing(false);
        setIsEnding(false);
        setError(message);
        pushLog('error', `Call error: ${message}`);
      });
    },
    [pushLog]
  );

  const initializeDevice = useCallback(async () => {
    clearAlerts();
    const token = accessToken.trim();
    if (!token) {
      setError(t('pages:test.twilio.errors.noToken', 'Please provide a Twilio Access Token first.'));
      return;
    }

    setIsInitializing(true);
    try {
      resetSession();
      const device = new Device(token, {
        logLevel: 1,
        closeProtection: false,
      });
      deviceRef.current = device;

      device.on('registering', () => {
        setDeviceState('registering');
        pushLog('info', 'Registering Twilio device...');
      });

      device.on('registered', () => {
        setDeviceState('registered');
        pushLog('success', 'Twilio device registered.');
      });

      device.on('unregistered', () => {
        setDeviceState('unregistered');
        pushLog('info', 'Twilio device unregistered.');
      });

      device.on('incoming', (incomingCall: Call) => {
        pushLog('warning', 'Incoming call received in test tab (auto-rejected).');
        incomingCall.reject();
      });

      device.on('tokenWillExpire', () => {
        pushLog(
          'warning',
          t(
            'pages:test.twilio.logs.tokenWillExpire',
            'Access token will expire soon. Refresh token to avoid call interruption.'
          )
        );
      });

      device.on('error', (deviceError: any) => {
        const message = stringifyError(deviceError);
        setDeviceState('error');
        setError(message);
        pushLog('error', `Device error: ${message}`);
      });

      await device.register();
      setInfo(t('pages:test.twilio.info.deviceReady', 'Twilio device is ready.'));
    } catch (initError) {
      const message = stringifyError(initError);
      setDeviceState('error');
      setError(message);
      pushLog('error', `Initialize device failed: ${message}`);
    } finally {
      setIsInitializing(false);
    }
  }, [accessToken, pushLog, resetSession, t]);

  const handleDial = useCallback(async () => {
    clearAlerts();
    const device = deviceRef.current;
    if (!device || deviceState !== 'registered') {
      setError(t('pages:test.twilio.errors.deviceNotReady', 'Please initialize and register device first.'));
      return;
    }
    if (!toNumber.trim()) {
      setError(t('pages:test.twilio.errors.noTarget', 'Please enter a target phone number.'));
      return;
    }
    if (callRef.current) {
      setError(t('pages:test.twilio.errors.callAlreadyActive', 'A call is already active.'));
      return;
    }

    setIsDialing(true);
    setCallState('dialing');
    pushLog('info', `Dialing ${toNumber.trim()} ...`);

    try {
      const params: Record<string, string> = {
        To: toNumber.trim(),
        identity: identity.trim() || 'webcall-tester',
      };
      if (selectedPromptCode) {
        params.prompt_code = selectedPromptCode;
      }

      const call = await device.connect({ params });
      callRef.current = call;
      bindCallEvents(call);
      setCallSid(call.parameters?.CallSid || '');
    } catch (dialError) {
      const message = stringifyError(dialError);
      setCallState('error');
      setIsDialing(false);
      setError(message);
      pushLog('error', `Dial failed: ${message}`);
    }
  }, [bindCallEvents, deviceState, identity, pushLog, selectedPromptCode, t, toNumber]);

  const handleHangUp = useCallback(() => {
    clearAlerts();
    const call = callRef.current;
    if (!call) return;

    try {
      setIsEnding(true);
      setCallState('ending');
      call.disconnect();
      pushLog('info', 'Disconnect requested.');
    } catch (endError) {
      const message = stringifyError(endError);
      setIsEnding(false);
      setCallState('error');
      setError(message);
      pushLog('error', `Disconnect failed: ${message}`);
    }
  }, [pushLog]);

  const handleToggleMute = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    call.mute(!isMuted);
  }, [isMuted]);

  const handleUnregister = useCallback(async () => {
    const device = deviceRef.current;
    if (!device) return;
    clearAlerts();
    try {
      await device.unregister();
      setDeviceState('unregistered');
      pushLog('info', 'Device unregistered.');
    } catch (unregisterError) {
      const message = stringifyError(unregisterError);
      setError(message);
      pushLog('error', `Unregister failed: ${message}`);
    }
  }, [pushLog]);

  const activePrompt = prompts.find((item) => item.code === selectedPromptCode);
  const canMute = callState === 'in_call';
  const canHangup = !!callRef.current && ['dialing', 'ringing', 'in_call', 'ending'].includes(callState);

  const deviceTagType = useMemo(() => {
    if (deviceState === 'registered') return 'green';
    if (deviceState === 'registering') return 'teal';
    if (deviceState === 'error') return 'red';
    if (deviceState === 'unregistered') return 'warm-gray';
    return 'cool-gray';
  }, [deviceState]);

  const callTagType = useMemo(() => {
    if (callState === 'in_call') return 'green';
    if (callState === 'dialing' || callState === 'ringing' || callState === 'ending') return 'teal';
    if (callState === 'error') return 'red';
    if (callState === 'ended') return 'warm-gray';
    return 'cool-gray';
  }, [callState]);

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {(error || info) && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            {error && (
              <InlineNotification
                kind="error"
                title={t('pages:test.twilio.notifications.error', 'Request failed')}
                subtitle={error}
                lowContrast
                onCloseButtonClick={() => setError(null)}
              />
            )}
            {info && (
              <InlineNotification
                kind="success"
                title={t('pages:test.twilio.notifications.success', 'Success')}
                subtitle={info}
                lowContrast
                onCloseButtonClick={() => setInfo(null)}
              />
            )}
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          <Tile className={styles.mainTile}>
            <div className={styles.header}>
              <div>
                <h3 className="cds--heading-03">
                  {t('pages:test.twilio.title', 'Twilio 拨号测试台')}
                </h3>
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

            <Stack gap={6}>
              <div className={styles.formGrid}>
                <TextInput
                  id="twilio-identity"
                  labelText={t('pages:test.twilio.form.identity', 'Client Identity')}
                  value={identity}
                  onChange={(event) => setIdentity(event.target.value)}
                  placeholder="webcall-tester"
                />
                <TextInput
                  id="twilio-dial-number"
                  labelText={t('pages:test.twilio.form.toNumber', 'Target Number (E.164)')}
                  value={toNumber}
                  onChange={(event) => setToNumber(event.target.value)}
                  placeholder="+819012345678"
                />
                {loadingPrompts ? (
                  <InlineLoading description={t('pages:test.twilio.loading.prompts', 'Loading prompts...')} />
                ) : (
                  <Select
                    id="twilio-prompt-code"
                    labelText={t('pages:test.twilio.form.prompt', 'Prompt Template')}
                    value={selectedPromptCode}
                    onChange={(event) => setSelectedPromptCode(event.target.value)}
                  >
                    {prompts.map((prompt) => (
                      <SelectItem key={prompt.id} value={prompt.code} text={prompt.name} />
                    ))}
                  </Select>
                )}
              </div>

              <div className={styles.actions}>
                <Button
                  kind="primary"
                  size="sm"
                  onClick={handleDial}
                  disabled={isDialing || isEnding || deviceState !== 'registered'}
                >
                  {t('pages:test.twilio.actions.dial', '开始拨号')}
                </Button>
                <Button
                  kind="secondary"
                  size="sm"
                  onClick={handleHangUp}
                  disabled={!canHangup || isEnding}
                >
                  {t('pages:test.twilio.actions.hangup', '挂断')}
                </Button>
                <Button
                  kind="tertiary"
                  size="sm"
                  onClick={handleToggleMute}
                  disabled={!canMute}
                >
                  {isMuted
                    ? t('pages:test.twilio.actions.unmute', '取消静音')
                    : t('pages:test.twilio.actions.mute', '静音')}
                </Button>
                <Button kind="ghost" size="sm" onClick={() => setLogs([])}>
                  {t('pages:test.twilio.actions.clearLogs', '清空日志')}
                </Button>
              </div>

              <dl className={styles.metaList}>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.twilio.meta.callSid', 'Call SID')}</dt>
                  <dd>{callSid || '-'}</dd>
                </div>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.twilio.meta.prompt', 'Selected Prompt')}</dt>
                  <dd>{activePrompt ? `${activePrompt.name} (${activePrompt.code})` : '-'}</dd>
                </div>
                <div className={styles.metaRow}>
                  <dt>{t('pages:test.twilio.meta.endpoint', 'Token Endpoint')}</dt>
                  <dd>{useEndpoint ? tokenEndpoint : t('pages:test.twilio.meta.manualToken', 'Manual token mode')}</dd>
                </div>
              </dl>

              <div className={styles.logPanel}>
                <h4 className="cds--heading-01">{t('pages:test.twilio.logs.title', '事件日志')}</h4>
                {logs.length === 0 ? (
                  <p className={styles.emptyLog}>
                    {t('pages:test.twilio.logs.empty', '暂无日志，执行一次初始化或拨号后会显示事件。')}
                  </p>
                ) : (
                  <ul className={styles.logList}>
                    {logs.map((log) => (
                      <li key={log.id} className={styles.logItem}>
                        <span className={styles.logTime}>
                          {log.time.toLocaleTimeString('ja-JP', { hour12: false })}
                        </span>
                        <span className={`${styles.logLevel} ${styles[`logLevel${log.level}`]}`}>
                          {log.level.toUpperCase()}
                        </span>
                        <span className={styles.logMessage}>{log.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Stack>
          </Tile>
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <Tile className={styles.panelTile}>
              <h4 className="cds--heading-01">
                {t('pages:test.twilio.sections.device', 'Device 与 Token')}
              </h4>
              <p className={styles.description}>
                {t(
                  'pages:test.twilio.sections.deviceDescription',
                  '支持从后端拉取 Token，也支持手动粘贴 Token 进行联调。'
                )}
              </p>

              <Toggle
                id="twilio-use-endpoint"
                labelText={t('pages:test.twilio.form.useEndpoint', '使用 Token Endpoint')}
                labelA={t('pages:test.twilio.form.manual', '手动')}
                labelB={t('pages:test.twilio.form.endpoint', '端点')}
                toggled={useEndpoint}
                onToggle={(value) => setUseEndpoint(value)}
              />

              <TextInput
                id="twilio-token-endpoint"
                labelText={t('pages:test.twilio.form.endpointUrl', 'Token Endpoint URL')}
                value={tokenEndpoint}
                onChange={(event) => setTokenEndpoint(event.target.value)}
                disabled={!useEndpoint}
                placeholder={`${API_BASE_URL}/twilio/token`}
              />

              <TextArea
                id="twilio-access-token"
                labelText={t('pages:test.twilio.form.token', 'Twilio Access Token')}
                value={accessToken}
                onChange={(event) => setAccessToken(event.target.value)}
                rows={8}
              />

              <div className={styles.buttonGroup}>
                <Button kind="primary" size="sm" onClick={() => void fetchToken()} disabled={!useEndpoint || isFetchingToken}>
                  {t('pages:test.twilio.actions.fetchToken', '获取 Token')}
                </Button>
                <Button kind="secondary" size="sm" onClick={() => void initializeDevice()} disabled={isInitializing}>
                  {t('pages:test.twilio.actions.initDevice', '初始化 Device')}
                </Button>
                <Button kind="tertiary" size="sm" onClick={() => void handleUnregister()} disabled={!deviceRef.current}>
                  {t('pages:test.twilio.actions.unregister', '注销 Device')}
                </Button>
                <Button kind="ghost" size="sm" onClick={resetSession}>
                  {t('pages:test.twilio.actions.reset', '重置会话')}
                </Button>
              </div>
            </Tile>

            <Tile className={styles.panelTile}>
              <h4 className="cds--heading-01">
                {t('pages:test.twilio.sections.guide', '集成检查清单')}
              </h4>
              <ul className={styles.checkList}>
                <li>{t('pages:test.twilio.guide.step1', 'Twilio Console 中创建 Voice TwiML App，并配置 Voice URL。')}</li>
                <li>{t('pages:test.twilio.guide.step2', '后端提供 Access Token 接口（建议 GET /api/v1/twilio/token?identity=...）。')}</li>
                <li>{t('pages:test.twilio.guide.step3', '来电/去电参数中附带 prompt_code，后端映射到当前 Prompt 模板。')}</li>
                <li>{t('pages:test.twilio.guide.step4', '联调完成后，在通话记录页核对 Call SID、状态与摘要是否一致。')}</li>
              </ul>
              <div className={styles.buttonGroup}>
                <Button kind="ghost" size="sm" onClick={() => navigate('/calls')}>
                  {t('pages:test.unified.actions.viewCalls', '查看通话记录')}
                </Button>
              </div>
            </Tile>
          </Stack>
        </Column>
      </Grid>
    </div>
  );
}
