import { useCallback, useRef, useState } from 'react';

import { submitAppointmentRecord } from '../../../api/appointments';
import { ChatMessage } from '../components/websocket/types';
import {
  buildRawTranscript,
  composeAppointmentPayload,
  extractAppointmentFromText,
  ParsedAppointment,
} from '../utils/appointment';

const FINAL_CONFIRMATION_PHRASES = ['ご予約内容を受付いたしました', 'ご利用ありがとうございます'];

const containsClosingPhrase = (text: string) =>
  FINAL_CONFIRMATION_PHRASES.every((phrase) => text.includes(phrase));

const operationLabelMap: Record<'create' | 'update' | 'delete', string> = {
  create: '新增预约',
  update: '修改预约',
  delete: '取消预约',
};

type UseAppointmentRecorderParams = {
  enabled: boolean;
  messages: ChatMessage[];
  onCreated?: () => Promise<void> | void;
  onAutoCreate?: () => void;
};

type AppointmentRecorder = {
  message: string | null;
  saving: boolean;
  handleAssistantMessage: (content: string) => void;
  createAppointment: (options?: { auto?: boolean }) => Promise<void>;
  reset: () => void;
};

export function useAppointmentRecorder({
  enabled,
  messages,
  onCreated,
  onAutoCreate,
}: UseAppointmentRecorderParams): AppointmentRecorder {
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const structuredAppointmentRef = useRef<ParsedAppointment | null>(null);
  const autoTriggeredRef = useRef(false);

  const createAppointment = useCallback(
    async (options?: { auto?: boolean }) => {
      if (!enabled) {
        setMessage('当前 Prompt 未开启预约功能。');
        return;
      }
      if (!messages.length) {
        setMessage('暂无对话记录，无法生成预约。');
        return;
      }
      const structured = structuredAppointmentRef.current;
      if (!structured) {
        setMessage('尚未检测到预约摘要，请确认模型输出 JSON。');
        return;
      }
      setSaving(true);
      setMessage(options?.auto ? '通话结束，正在生成预约记录…' : '正在生成预约记录...');
      const previousAutoFlag = autoTriggeredRef.current;
      autoTriggeredRef.current = true;
      try {
        const transcript = buildRawTranscript(
          messages.map((messageItem) => ({
            role: messageItem.role,
            text: messageItem.content,
            timestamp: messageItem.timestamp,
          })),
        );
        await submitAppointmentRecord(composeAppointmentPayload(structured, transcript));
        structuredAppointmentRef.current = null;
        await onCreated?.();
        setMessage(
          options?.auto
            ? `通话结束，已完成${operationLabelMap[structured.operation]}。`
            : `已完成${operationLabelMap[structured.operation]}，前往「预约记录」查看。`,
        );
        if (options?.auto) {
          onAutoCreate?.();
        }
      } catch (error) {
        console.error('生成预约失败', error);
        setMessage('生成预约记录失败，请稍后再试。');
        autoTriggeredRef.current = previousAutoFlag;
      } finally {
        setSaving(false);
      }
    },
    [enabled, messages, onAutoCreate, onCreated],
  );

  const handleAssistantMessage = useCallback(
    (content: string) => {
      if (!enabled) return;
      const parsed = extractAppointmentFromText(content);
      if (parsed) {
        structuredAppointmentRef.current = parsed;
        setMessage('已捕获预约摘要，可生成记录。');
      }
      if (containsClosingPhrase(content) && !autoTriggeredRef.current) {
        if (!structuredAppointmentRef.current) {
          setMessage('检测到结束语，但未解析到预约摘要，请确保输出 JSON。');
          return;
        }
        void createAppointment({ auto: true });
      }
    },
    [createAppointment, enabled],
  );

  const reset = useCallback(() => {
    structuredAppointmentRef.current = null;
    autoTriggeredRef.current = false;
    setMessage(null);
    setSaving(false);
  }, []);

  return {
    message,
    saving,
    handleAssistantMessage,
    createAppointment,
    reset,
  };
}
