import type { FinalizeTestSessionResponse, StartTestSessionResponse } from '../../api/testLab';

interface TranslateFn {
  (key: string, fallback: string): string;
}

interface SessionStatusInput {
  session: StartTestSessionResponse | null;
  finalizeResult: FinalizeTestSessionResponse | null;
}

interface SessionStatusView {
  sessionClosed: boolean;
  sessionStatus: string;
}

export function buildQuickMessages(t: TranslateFn): string[] {
  return [
    t('pages:test.unified.chat.quickExamples.companyIntro', 'ABC会社のCCCです。'),
    t('pages:test.unified.chat.quickExamples.dateRequest', '2026年4月1日に粗大ゴミを回収してほしいです。'),
    t('pages:test.unified.chat.quickExamples.address', '回収場所は東京都千代田区神田2-4-33です。'),
    t('pages:test.unified.chat.quickExamples.items', 'オフィス机2台と椅子4脚で、量はおよそ2立方メートルです。'),
    t('pages:test.unified.chat.quickExamples.confirmation', 'はい、その内容で予約をお願いします。'),
    t('pages:test.unified.chat.quickExamples.changeDate', '回収日を4月5日に変更できますか？'),
    t('pages:test.unified.chat.quickExamples.addFridge', '古い冷蔵庫も1台追加したいのですが。'),
    t('pages:test.unified.chat.quickExamples.cancelRequest', 'すみません、やっぱり予約をキャンセルしたいです。'),
  ];
}

export function deriveSessionStatus(
  { session, finalizeResult }: SessionStatusInput,
  t: TranslateFn
): SessionStatusView {
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

  return {
    sessionClosed,
    sessionStatus,
  };
}
