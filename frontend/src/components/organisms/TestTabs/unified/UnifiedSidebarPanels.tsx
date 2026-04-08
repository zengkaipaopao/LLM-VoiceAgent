import { Stack } from '@carbon/react';

import { FinalizeTestSessionResponse, StartTestSessionResponse } from '../../../../api/testLab';
import { PromptTemplate } from '../../../../types/shared';
import { UnifiedRecordLinkagePanel } from './UnifiedRecordLinkagePanel';
import { UnifiedSessionDetailsPanel } from './UnifiedSessionDetailsPanel';
import { UnifiedSetupPanel } from './UnifiedSetupPanel';

interface UnifiedSidebarPanelsProps {
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  callerName: string;
  setCallerName: (value: string) => void;
  hasSession: boolean;
  sessionClosed: boolean;
  isStarting: boolean;
  isSending: boolean;
  isFinalizing: boolean;
  canClearPanel: boolean;
  onStartSession: () => Promise<void>;
  onFinalize: () => Promise<void>;
  onClear: () => Promise<void>;
  selectedPrompt: PromptTemplate | undefined;
  session: StartTestSessionResponse | null;
  totalTokens: number;
  finalizeResult: FinalizeTestSessionResponse | null;
  onViewCalls: () => void;
  onViewAppointments: () => void;
}

export function UnifiedSidebarPanels({
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  callerName,
  setCallerName,
  hasSession,
  sessionClosed,
  isStarting,
  isSending,
  isFinalizing,
  canClearPanel,
  onStartSession,
  onFinalize,
  onClear,
  selectedPrompt,
  session,
  totalTokens,
  finalizeResult,
  onViewCalls,
  onViewAppointments,
}: UnifiedSidebarPanelsProps) {
  return (
    <Stack gap={6}>
      <UnifiedSetupPanel
        loadingPrompts={loadingPrompts}
        prompts={prompts}
        selectedPromptCode={selectedPromptCode}
        setSelectedPromptCode={setSelectedPromptCode}
        callerName={callerName}
        setCallerName={setCallerName}
        hasSession={hasSession}
        sessionClosed={sessionClosed}
        isStarting={isStarting}
        isSending={isSending}
        isFinalizing={isFinalizing}
        canClearPanel={canClearPanel}
        onStartSession={onStartSession}
        onFinalize={onFinalize}
        onClear={onClear}
      />

      <UnifiedSessionDetailsPanel
        selectedPrompt={selectedPrompt}
        session={session}
        totalTokens={totalTokens}
      />

      <UnifiedRecordLinkagePanel
        finalizeResult={finalizeResult}
        onViewCalls={onViewCalls}
        onViewAppointments={onViewAppointments}
      />
    </Stack>
  );
}
