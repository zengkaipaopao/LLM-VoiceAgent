import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Column,
  Grid,
  InlineNotification,
  Loading,
  Select,
  SelectItem,
  Stack,
  Tag,
  TextInput,
  Tile,
} from '@carbon/react';

import { API_BASE_URL } from '../../../api/http';
import { fetchPrompts } from '../../../api/prompts';
import {
  finalizeTestSession,
  FinalizeTestSessionResponse,
  startTestSession,
  StartTestSessionResponse,
} from '../../../api/testLab';
import { Message } from '../../../hooks/useChatStream';
import { PromptTemplate } from '../../../types/shared';
import { ChatInput } from '../../molecules/ChatInput';
import { MessageList } from '../MessageList';
import styles from './UnifiedTestLabTabContent.module.scss';

type StreamEvent = {
  type: 'call_id' | 'content' | 'done' | 'error';
  call_id?: string;
  content?: string;
  error?: string;
  tokens_used?: number;
};

function sanitizeAssistantPrefix(text: string): string {
  return text.replace(
    /^\s*(?:assistant|ai\s*assistant|ai助手|助手|アシスタント|aiアシスタント)\s*[:：]\s*/i,
    ''
  );
}

function parseSSEEvent(rawEvent: string): StreamEvent | null {
  const dataLines = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (!dataLines.length) return null;

  const payload = dataLines.join('\n').trim();
  if (!payload) return null;

  try {
    return JSON.parse(payload) as StreamEvent;
  } catch {
    return null;
  }
}

export function UnifiedTestLabTabContent() {
  const navigate = useNavigate();
  const { t } = useTranslation(['pages']);

  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [selectedPromptCode, setSelectedPromptCode] = useState('');

  const [callerName, setCallerName] = useState('Test Caller');
  const [session, setSession] = useState<StartTestSessionResponse | null>(null);
  const sessionRef = useRef<StartTestSessionResponse | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [totalTokens, setTotalTokens] = useState(0);
  const [finalizeResult, setFinalizeResult] = useState<FinalizeTestSessionResponse | null>(null);

  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const activeTemplateCode = session?.template_code || selectedPromptCode;
  const selectedPrompt = prompts.find((item) => item.code === activeTemplateCode);
  const quickMessages = useMemo(
    () => [
      t('pages:test.unified.chat.quickExamples.companyIntro', 'ABC会社のCCCです。'),
      t(
        'pages:test.unified.chat.quickExamples.dateRequest',
        '2026年4月1日に粗大ゴミを回収してほしいです。'
      ),
      t(
        'pages:test.unified.chat.quickExamples.address',
        '回収場所は東京都千代田区神田2-4-33です。'
      ),
      t(
        'pages:test.unified.chat.quickExamples.items',
        'オフィス机2台と椅子4脚で、量はおよそ2立方メートルです。'
      ),
      t(
        'pages:test.unified.chat.quickExamples.confirmation',
        'はい、その内容で予約をお願いします。'
      ),
    ],
    [t]
  );

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
        setError(
          t(
            'pages:test.unified.errors.loadPrompts',
            'Failed to load prompt list. Please check backend connection.'
          )
        );
        console.error(loadError);
      } finally {
        setLoadingPrompts(false);
      }
    };

    loadPrompts();
  }, [t]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const createSession = useCallback(async () => {
    if (!selectedPromptCode) {
      throw new Error(t('pages:test.unified.errors.noPromptSelected', 'Please select a prompt first'));
    }

    setIsStarting(true);
    setError(null);
    setInfo(null);

    try {
      const created = await startTestSession({
        template_code: selectedPromptCode,
        caller_name: callerName.trim() || undefined,
      });

      setSession(created);
      sessionRef.current = created;
      setMessages([]);
      setTotalTokens(0);
      setFinalizeResult(null);
      setInfo(
        t('pages:test.unified.info.sessionCreated', 'Test session created: {{phone}}', {
          phone: created.simulated_phone,
        })
      );

      return created;
    } finally {
      setIsStarting(false);
    }
  }, [callerName, selectedPromptCode, t]);

  const handleStartSession = async () => {
    try {
      await createSession();
    } catch (startError: any) {
      setError(
        startError?.response?.data?.detail ||
          startError?.message ||
          t('pages:test.unified.errors.createSessionFailed', 'Failed to create session')
      );
    }
  };

  const appendErrorMessage = (message: string) => {
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: `❌ ${message}`,
        timestamp: new Date(),
      },
    ]);
  };

  const handleSendMessage = async (content: string) => {
    if (isSending || isFinalizing) {
      return;
    }

    let activeSession = sessionRef.current;
    try {
      setError(null);
      setInfo(null);

      if (!activeSession) {
        activeSession = await createSession();
      }

      setIsSending(true);

      const userMessage: Message = {
        role: 'user',
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      abortControllerRef.current = new AbortController();

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          call_id: activeSession.call_id,
          message: content,
          template_code: activeSession.template_code || selectedPromptCode,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(
          t('pages:test.unified.errors.requestFailedWithStatus', 'Request failed: {{status}}', {
            status: response.status,
          })
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let assistantContent = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        const decodedChunk = decoder.decode(value || new Uint8Array(), { stream: !done });
        buffer += decodedChunk.replace(/\r\n/g, '\n');

        let boundaryIndex = buffer.indexOf('\n\n');

        while (boundaryIndex !== -1) {
          const rawEvent = buffer.slice(0, boundaryIndex);
          buffer = buffer.slice(boundaryIndex + 2);

          const eventPayload = parseSSEEvent(rawEvent);
          if (eventPayload) {
            if (eventPayload.type === 'call_id' && eventPayload.call_id && activeSession) {
              const updatedSession = {
                ...activeSession,
                call_id: eventPayload.call_id,
              };
              activeSession = updatedSession;
              setSession(updatedSession);
              sessionRef.current = updatedSession;
            }

            if (eventPayload.type === 'content' && typeof eventPayload.content === 'string') {
              assistantContent += eventPayload.content;
              const sanitizedAssistantContent = sanitizeAssistantPrefix(assistantContent);
              setMessages((prev) => {
                const next = [...prev];
                if (next.length > 0) {
                  next[next.length - 1] = {
                    ...assistantMessage,
                    content: sanitizedAssistantContent,
                  };
                }
                return next;
              });
            }

            if (eventPayload.type === 'done' && typeof eventPayload.tokens_used === 'number') {
              setTotalTokens((prev) => prev + eventPayload.tokens_used);
            }

            if (eventPayload.type === 'error') {
              throw new Error(
                eventPayload.error ||
                  t('pages:test.unified.errors.streamFailed', 'Streaming response failed')
              );
            }
          }

          boundaryIndex = buffer.indexOf('\n\n');
        }

        if (done) {
          const tailEvent = parseSSEEvent(buffer);
          if (tailEvent?.type === 'error') {
            throw new Error(
              tailEvent.error || t('pages:test.unified.errors.streamFailed', 'Streaming response failed')
            );
          }
          if (tailEvent?.type === 'done' && typeof tailEvent.tokens_used === 'number') {
            setTotalTokens((prev) => prev + tailEvent.tokens_used);
          }
          break;
        }
      }
    } catch (sendError: any) {
      if (sendError?.name !== 'AbortError') {
        const message =
          sendError?.response?.data?.detail ||
          sendError?.message ||
          t('pages:test.unified.errors.sendMessageFailed', 'Failed to send message');
        setError(message);
        appendErrorMessage(message);
      }
    } finally {
      setIsSending(false);
      abortControllerRef.current = null;
    }
  };

  const handleFinalize = async () => {
    const activeSession = sessionRef.current;
    if (!activeSession) {
      setError(
        t('pages:test.unified.errors.noActiveSession', 'Please create a test session first')
      );
      return;
    }

    setIsFinalizing(true);
    setError(null);
    setInfo(null);

    try {
      const result = await finalizeTestSession({
        call_id: activeSession.call_id,
        template_code: activeSession.template_code || selectedPromptCode,
        run_extraction: true,
      });

      setFinalizeResult(result);
      setInfo(
        result.extraction?.message ||
          t('pages:test.unified.info.sessionFinalized', 'Session finalized and extraction completed')
      );
    } catch (finalizeError: any) {
      setError(
        finalizeError?.response?.data?.detail ||
          finalizeError?.message ||
          t('pages:test.unified.errors.finalizeFailed', 'Failed to finalize session')
      );
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setTotalTokens(0);
    setFinalizeResult(null);
    setError(null);
    setInfo(null);
  };

  const sessionClosed =
    !!session &&
    !!finalizeResult &&
    finalizeResult.call_id === session.call_id &&
    finalizeResult.status === 'completed';
  const sessionStatus = sessionClosed
    ? t('pages:test.unified.status.completed', 'Completed')
    : session
      ? t('pages:test.unified.status.active', 'Active')
      : t('pages:test.unified.status.notStarted', 'Not started');

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        {(error || info) && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            {error && (
              <InlineNotification
                kind="error"
                title={t('pages:test.unified.notifications.errorTitle', 'Request failed')}
                subtitle={error}
                lowContrast
                onCloseButtonClick={() => setError(null)}
              />
            )}
            {info && (
              <InlineNotification
                kind="success"
                title={t('pages:test.unified.notifications.successTitle', 'Success')}
                subtitle={info}
                lowContrast
                onCloseButtonClick={() => setInfo(null)}
              />
            )}
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          <Tile className={styles.chatTile}>
            <div className={styles.chatHeader}>
              <div>
                <h3 className="cds--heading-03">
                  {t('pages:test.unified.sections.chatTitle', 'Conversation Workspace')}
                </h3>
                <p className={styles.sectionDescription}>
                  {t(
                    'pages:test.unified.sections.chatDescription',
                    'Send messages to test prompt behavior, action triggering, and extraction quality in one flow.'
                  )}
                </p>
              </div>
              <Tag type={sessionClosed ? 'blue' : session ? 'green' : 'warm-gray'}>
                {sessionStatus}
              </Tag>
            </div>

            <MessageList messages={messages} isLoading={isSending} />
            <ChatInput
              onSend={(value) => {
                void handleSendMessage(value);
              }}
              disabled={!selectedPromptCode || isStarting || isSending || isFinalizing || sessionClosed}
              quickMessages={quickMessages}
              quickMessagesLabel={t('pages:test.unified.chat.quickInputLabel', '快捷输入')}
              placeholder={
                sessionClosed
                  ? t(
                      'pages:test.unified.chat.closedPlaceholder',
                      'This session is closed. Click "New Session" to continue testing.'
                    )
                  : t(
                      'pages:test.unified.chat.inputPlaceholder',
                      'Type a message to test prompt behavior and action extraction...'
                    )
              }
            />
          </Tile>
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <Tile className={styles.panelTile}>
              <div>
                <h4 className="cds--heading-01">
                  {t('pages:test.unified.sections.setupTitle', 'Session Setup')}
                </h4>
                <p className={styles.sectionDescription}>
                  {t(
                    'pages:test.unified.sections.setupDescription',
                    'Choose a prompt and create a simulation session before or during chat.'
                  )}
                </p>
              </div>

              <div className={styles.formFields}>
                {loadingPrompts ? (
                  <Loading small withOverlay={false} />
                ) : (
                  <Select
                    id="test-lab-prompt"
                    labelText={t('pages:test.unified.form.promptLabel', 'Select Prompt Model')}
                    value={selectedPromptCode}
                    onChange={(event) => setSelectedPromptCode(event.target.value)}
                    size="sm"
                    disabled={isStarting || isSending || isFinalizing}
                  >
                    {prompts.map((prompt) => (
                      <SelectItem key={prompt.id} value={prompt.code} text={prompt.name} />
                    ))}
                  </Select>
                )}

                <TextInput
                  id="test-lab-caller"
                  labelText={t('pages:test.unified.form.callerLabel', 'Simulated Caller Name')}
                  value={callerName}
                  onChange={(event) => setCallerName(event.target.value)}
                  size="sm"
                  placeholder={t('pages:test.unified.form.callerPlaceholder', 'Test Caller')}
                  disabled={isStarting || isSending || isFinalizing}
                />
              </div>

              <div className={styles.buttonGroup}>
                <Button
                  kind="primary"
                  size="sm"
                  onClick={handleStartSession}
                  disabled={!selectedPromptCode || isStarting || isSending || isFinalizing}
                >
                  {session
                    ? t('pages:test.unified.actions.newSession', 'New Session')
                    : t('pages:test.unified.actions.startSession', 'Start Session')}
                </Button>
                <Button
                  kind="secondary"
                  size="sm"
                  onClick={handleFinalize}
                  disabled={!session || isStarting || isSending || isFinalizing || sessionClosed}
                >
                  {t('pages:test.unified.actions.finalize', 'Finalize & Extract')}
                </Button>
                <Button
                  kind="ghost"
                  size="sm"
                  onClick={handleClear}
                  disabled={messages.length === 0 && !error && !info}
                >
                  {t('pages:test.unified.actions.clearPanel', 'Clear Panel')}
                </Button>
              </div>
            </Tile>

            <Tile className={styles.panelTile}>
              <div>
                <h4 className="cds--heading-01">
                  {t('pages:test.unified.sections.detailsTitle', 'Session Details')}
                </h4>
                <p className={styles.sectionDescription}>
                  {t(
                    'pages:test.unified.sections.detailsDescription',
                    'Track current model, call metadata, and token usage for this test run.'
                  )}
                </p>
              </div>

              {selectedPrompt && (
                <p className={styles.promptInfo}>
                  {t(
                    'pages:test.unified.meta.currentModel',
                    'Model: {{provider}}/{{model}} · Temp {{temperature}}',
                    {
                      provider: selectedPrompt.llmProvider,
                      model: selectedPrompt.llmModel,
                      temperature: selectedPrompt.temperature,
                    }
                  )}
                </p>
              )}

              {session ? (
                <dl className={styles.metaList}>
                  <div className={styles.metaRow}>
                    <dt>{t('pages:test.unified.meta.callIdLabel', 'Call ID')}</dt>
                    <dd>{session.call_id}</dd>
                  </div>
                  <div className={styles.metaRow}>
                    <dt>{t('pages:test.unified.meta.phoneLabel', 'Simulated Phone')}</dt>
                    <dd>{session.simulated_phone}</dd>
                  </div>
                  <div className={styles.metaRow}>
                    <dt>{t('pages:test.unified.meta.templateLabel', 'Template')}</dt>
                    <dd>{session.template_code}</dd>
                  </div>
                  <div className={styles.metaRow}>
                    <dt>{t('pages:test.unified.meta.tokensLabel', 'Total Tokens')}</dt>
                    <dd>{totalTokens}</dd>
                  </div>
                </dl>
              ) : (
                <p className={styles.sectionDescription}>
                  {t(
                    'pages:test.unified.sections.noSession',
                    'No active session yet. Start a session to display metadata.'
                  )}
                </p>
              )}
            </Tile>

            <Tile className={styles.panelTile}>
              <div>
                <h4 className="cds--heading-01">
                  {t('pages:test.unified.records.title', 'Record Linkage')}
                </h4>
                <p className={styles.sectionDescription}>
                  {t(
                    'pages:test.unified.records.description',
                    'Test data is written to Calls/Appointments and can be reviewed immediately.'
                  )}
                  {finalizeResult?.appointment_id
                    ? t('pages:test.unified.records.currentAppointment', ' Current appointment ID: {{id}}', {
                        id: finalizeResult.appointment_id,
                      })
                    : ''}
                </p>
              </div>

              <div className={styles.buttonGroup}>
                <Button kind="tertiary" size="sm" onClick={() => navigate('/calls')}>
                  {t('pages:test.unified.actions.viewCalls', 'View Calls')}
                </Button>
                <Button kind="tertiary" size="sm" onClick={() => navigate('/appointments')}>
                  {t('pages:test.unified.actions.viewAppointments', 'View Appointments')}
                </Button>
              </div>
            </Tile>
          </Stack>
        </Column>
      </Grid>
    </div>
  );
}
