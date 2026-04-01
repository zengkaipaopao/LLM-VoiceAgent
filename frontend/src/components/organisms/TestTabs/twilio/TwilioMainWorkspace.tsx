import { Stack, Tile } from '@carbon/react';

import { PromptTemplate } from '../../../../types/shared';
import {
  CallState,
  DeviceState,
  EventLog,
  TwilioStatusTagType,
} from '../../../../hooks/useTwilioWebCallConsole';
import { TwilioBasicForm } from './TwilioBasicForm';
import { TwilioCallActions } from './TwilioCallActions';
import { TwilioLogPanel } from './TwilioLogPanel';
import { TwilioMetaList } from './TwilioMetaList';
import { TwilioStatusHeader } from './TwilioStatusHeader';
import styles from '../TwilioTabContent.module.scss';

interface TwilioMainWorkspaceProps {
  deviceState: DeviceState;
  callState: CallState;
  deviceTagType: TwilioStatusTagType;
  callTagType: TwilioStatusTagType;
  identity: string;
  setIdentity: (value: string) => void;
  toNumber: string;
  setToNumber: (value: string) => void;
  loadingPrompts: boolean;
  prompts: PromptTemplate[];
  selectedPromptCode: string;
  setSelectedPromptCode: (value: string) => void;
  isDialing: boolean;
  isEnding: boolean;
  canHangup: boolean;
  canMute: boolean;
  isMuted: boolean;
  handleDial: () => Promise<void>;
  handleHangUp: () => void;
  handleToggleMute: () => void;
  clearLogs: () => void;
  callSid: string;
  activePrompt: PromptTemplate | undefined;
  useEndpoint: boolean;
  tokenEndpoint: string;
  logs: EventLog[];
}

export function TwilioMainWorkspace({
  deviceState,
  callState,
  deviceTagType,
  callTagType,
  identity,
  setIdentity,
  toNumber,
  setToNumber,
  loadingPrompts,
  prompts,
  selectedPromptCode,
  setSelectedPromptCode,
  isDialing,
  isEnding,
  canHangup,
  canMute,
  isMuted,
  handleDial,
  handleHangUp,
  handleToggleMute,
  clearLogs,
  callSid,
  activePrompt,
  useEndpoint,
  tokenEndpoint,
  logs,
}: TwilioMainWorkspaceProps) {
  return (
    <Tile className={styles.mainTile}>
      <TwilioStatusHeader
        deviceState={deviceState}
        callState={callState}
        deviceTagType={deviceTagType}
        callTagType={callTagType}
      />

      <Stack gap={6}>
        <TwilioBasicForm
          identity={identity}
          setIdentity={setIdentity}
          toNumber={toNumber}
          setToNumber={setToNumber}
          loadingPrompts={loadingPrompts}
          prompts={prompts}
          selectedPromptCode={selectedPromptCode}
          setSelectedPromptCode={setSelectedPromptCode}
        />

        <TwilioCallActions
          deviceState={deviceState}
          isDialing={isDialing}
          isEnding={isEnding}
          canHangup={canHangup}
          canMute={canMute}
          isMuted={isMuted}
          handleDial={handleDial}
          handleHangUp={handleHangUp}
          handleToggleMute={handleToggleMute}
          clearLogs={clearLogs}
        />

        <TwilioMetaList
          callSid={callSid}
          activePrompt={activePrompt}
          useEndpoint={useEndpoint}
          tokenEndpoint={tokenEndpoint}
        />

        <TwilioLogPanel logs={logs} />
      </Stack>
    </Tile>
  );
}
