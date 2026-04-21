import type { EventLog, LogLevel } from '../../../hooks/testTabs/eventLog';
import type { MicStatus, SocketStatus } from './hooks/useVoiceTestConsole';

export type GatewayLogLevel = 'info' | 'success' | 'warning' | 'error';

interface DialerLogItemLike {
  level: GatewayLogLevel;
  message: string;
}

interface TwilioTraceEventLike {
  seq: number;
  ts: number;
  type: string;
  level?: GatewayLogLevel;
  text?: string;
  final?: boolean;
}

export type VoiceDiagnosticStatus = 'ok' | 'warning' | 'error' | 'unknown';

export interface VoiceDiagnosticEvidence {
  label: string;
  text: string;
  level: LogLevel | GatewayLogLevel;
}

export interface VoiceDiagnostic {
  source: 'backend_trace' | 'frontend_direct' | 'frontend_gateway';
  status: VoiceDiagnosticStatus;
  category: string;
  owner: string;
  title: string;
  summary: string;
  actions: string[];
  evidence: VoiceDiagnosticEvidence[];
}

export interface BackendTraceDiagnosticResponse {
  call_sid: string;
  status: VoiceDiagnosticStatus;
  category: string;
  owner: string;
  title: string;
  summary: string;
  actions: string[];
  evidence: Array<{
    seq: number;
    ts: number;
    type: string;
    level: GatewayLogLevel;
    text: string;
  }>;
  last_seq: number;
  stream_active: boolean;
}

function toEvidence(
  label: string,
  text: string,
  level: LogLevel | GatewayLogLevel = 'info'
): VoiceDiagnosticEvidence {
  return { label, text, level };
}

function lastErrorLogs(logs: Array<EventLog | DialerLogItemLike>, limit = 3): VoiceDiagnosticEvidence[] {
  return [...logs]
    .reverse()
    .filter((item) => item.level === 'error' || item.level === 'warning')
    .slice(0, limit)
    .map((item) => toEvidence('日志', item.message, item.level));
}

function matchAny(text: string, tokens: string[]): boolean {
  return tokens.some((token) => text.includes(token));
}

export function mapBackendTraceDiagnostic(
  diagnostic: BackendTraceDiagnosticResponse | null | undefined
): VoiceDiagnostic | null {
  if (!diagnostic) {
    return null;
  }
  return {
    source: 'backend_trace',
    status: diagnostic.status,
    category: diagnostic.category,
    owner: diagnostic.owner,
    title: diagnostic.title,
    summary: diagnostic.summary,
    actions: diagnostic.actions,
    evidence: (diagnostic.evidence || []).map((item) =>
      toEvidence(item.type || 'trace', item.text || '-', item.level || 'info')
    ),
  };
}

export function classifyDirectVoiceDiagnostic(params: {
  socketStatus: SocketStatus;
  micStatus: MicStatus;
  error: string | null;
  logs: EventLog[];
  model: string;
}): VoiceDiagnostic | null {
  const { socketStatus, micStatus, error, logs, model } = params;
  const message = (error || '').trim();
  const lowered = message.toLowerCase();
  const evidence = message ? [toEvidence('错误', message, 'error'), ...lastErrorLogs(logs)] : lastErrorLogs(logs);

  if (!message && socketStatus === 'connected') {
    return {
      source: 'frontend_direct',
      status: 'ok',
      category: 'healthy',
      owner: 'system',
      title: '浏览器直连链路正常',
      summary: 'Gemini Live 直连会话当前没有看到明确错误。',
      actions: ['如果仍感觉不顺畅，继续观察浏览器控制台日志和网络面板。'],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['not gemini live', 'native audio', '当前模型不是 gemini live'])) {
    return {
      source: 'frontend_direct',
      status: 'error',
      category: 'direct_model_configuration',
      owner: 'prompt_or_model_config',
      title: '直连语音模型配置不兼容',
      summary: `当前浏览器直连测试使用的模型不是可用于 Gemini Live 语音会话的模型：${model || '(empty)'}`,
      actions: [
        '切换到 Gemini Live / Native Audio 模型。',
        '如果模型来自 Prompt，先修正 Prompt 的 llm_model。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['default credentials', 'permission denied', 'aiplatform.endpoints.predict'])) {
    return {
      source: 'frontend_direct',
      status: 'error',
      category: 'google_auth_or_iam',
      owner: 'google_cloud_auth',
      title: 'Gemini Live 认证或权限失败',
      summary: '浏览器虽然在走 ephemeral token，但后端签发或模型侧校验阶段出现了 Google Cloud 凭证 / IAM 错误。',
      actions: [
        '检查后端签发 ephemeral token 时使用的 GCP 身份。',
        '确认该身份有权访问目标 Gemini Live 模型。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['failed to start microphone', 'microphone', 'permission denied'])) {
    return {
      source: 'frontend_direct',
      status: 'error',
      category: 'browser_microphone',
      owner: 'browser_device',
      title: '浏览器麦克风不可用',
      summary: '直连会话可能已连上，但本地采音设备未能正常启动，模型收不到你的语音。',
      actions: [
        '检查浏览器是否允许麦克风权限。',
        '确认当前输入设备可用，没有被系统或其他软件占用。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['websocket connection error', 'failed to connect', 'closed (code'])) {
    return {
      source: 'frontend_direct',
      status: 'error',
      category: 'direct_transport',
      owner: 'browser_network',
      title: '浏览器到 Gemini Live 的连接失败',
      summary: '浏览器直连链路在 WebSocket 建连或保活阶段失败。',
      actions: [
        '检查本机网络、浏览器控制台和是否存在代理/防火墙拦截。',
        '如果是通过后端获取 token，再核对 token 是否过期或模型是否可用。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (message) {
    return {
      source: 'frontend_direct',
      status: socketStatus === 'error' ? 'error' : 'warning',
      category: 'direct_unknown',
      owner: 'frontend_or_backend',
      title: '浏览器直连链路出现未归类异常',
      summary: message,
      actions: [
        '查看会话事件日志中的最后几条 error / warning。',
        '如果问题稳定复现，保留错误原文和时间点继续排查。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  return null;
}

export function classifyGatewayFallbackDiagnostic(params: {
  error: string | null;
  dialerStatus: string;
  callStatus: string;
  logs: DialerLogItemLike[];
  traceEvents: TwilioTraceEventLike[];
}): VoiceDiagnostic | null {
  const { error, dialerStatus, callStatus, logs, traceEvents } = params;
  const message = (error || '').trim();
  const lowered = message.toLowerCase();
  const evidence = message ? [toEvidence('错误', message, 'error'), ...lastErrorLogs(logs)] : lastErrorLogs(logs);

  if (matchAny(lowered, ['accesstokeninvalid', '20101'])) {
    return {
      source: 'frontend_gateway',
      status: 'error',
      category: 'twilio_access_token',
      owner: 'twilio_credentials',
      title: 'Twilio Voice SDK Token 无效',
      summary: '浏览器拨号前的 Twilio Device 注册失败，问题发生在 Twilio Access Token 校验阶段。',
      actions: [
        '检查 TWILIO_API_KEY_SID、TWILIO_API_KEY_SECRET、TWILIO_ACCOUNT_SID 是否匹配同一项目。',
        '确认后端生成 token 的 identity、ttl 和 TwiML App SID 配置无误。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['注册设备失败', 'twilio device 错误'])) {
    return {
      source: 'frontend_gateway',
      status: 'error',
      category: 'twilio_device_registration',
      owner: 'twilio_device',
      title: 'Twilio 浏览器设备注册失败',
      summary: message || '浏览器端未能成功注册 Twilio Device。',
      actions: [
        '先看错误里是否包含具体 code/name，例如 AccessTokenInvalid。',
        '如果没有明确 code，再检查浏览器网络和 Twilio SDK 初始化参数。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (matchAny(lowered, ['拨号失败', '通话错误'])) {
    return {
      source: 'frontend_gateway',
      status: 'error',
      category: 'twilio_call_setup',
      owner: 'twilio_call_setup',
      title: 'Twilio 电话建立失败',
      summary: message || '浏览器侧已尝试拨号，但 Twilio 呼叫建立阶段失败。',
      actions: [
        '检查目标号码、Twilio 外呼权限和地域限制。',
        '对照 Twilio Console 中同一时间点的 Call 记录。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (!message && callStatus === 'in-call' && traceEvents.length === 0) {
    return {
      source: 'frontend_gateway',
      status: 'warning',
      category: 'trace_not_arrived',
      owner: 'backend_trace',
      title: '电话已接通，但后端还没有写入 trace',
      summary: '浏览器侧显示通话已经进入 in-call，但测试页尚未拿到任何后端 trace 事件。',
      actions: [
        '检查后端是否成功收到 Twilio 电话流并建立官方 Conversational Agents 会话。',
        '检查 Call SID 与 trace 轮询的 Call SID 是否一致。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  if (message) {
    return {
      source: 'frontend_gateway',
      status: dialerStatus === 'error' || callStatus === 'error' ? 'error' : 'warning',
      category: 'gateway_unknown',
      owner: 'frontend_or_twilio',
      title: '电话网关出现未归类异常',
      summary: message,
      actions: [
        '先查看拨号与链路日志，再查看后端 trace 诊断。',
        '保留错误原文、Call SID 和时间点用于追责。',
      ],
      evidence: evidence.slice(0, 3),
    };
  }

  return null;
}
