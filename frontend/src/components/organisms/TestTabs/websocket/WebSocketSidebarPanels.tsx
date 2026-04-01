import { Stack } from '@carbon/react';

import { EventLog } from '../../../../hooks/useLiveWebSocketConsole';
import { WebSocketSidePanels } from './WebSocketSidePanels';

interface WebSocketSidebarPanelsProps {
  inputTranscript: string;
  outputTranscript: string;
  assistantText: string;
  logs: EventLog[];
}

export function WebSocketSidebarPanels({
  inputTranscript,
  outputTranscript,
  assistantText,
  logs,
}: WebSocketSidebarPanelsProps) {
  return (
    <Stack gap={6}>
      <WebSocketSidePanels
        inputTranscript={inputTranscript}
        outputTranscript={outputTranscript}
        assistantText={assistantText}
        logs={logs}
      />
    </Stack>
  );
}
