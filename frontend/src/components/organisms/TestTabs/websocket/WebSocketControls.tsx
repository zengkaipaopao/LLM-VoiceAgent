import { Button, TextInput, Toggle } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { MicStatus, SocketStatus } from '../../../../hooks/useLiveWebSocketConsole';
import styles from '../WebSocketTabContent.module.scss';

interface WebSocketControlsProps {
  socketStatus: SocketStatus;
  micStatus: MicStatus;
  canUseRealtimeInput: boolean;
  textInput: string;
  setTextInput: (value: string) => void;
  connectSocket: () => void;
  disconnectSocket: () => void;
  clearConsole: () => void;
  sendText: () => void;
  toggleMicrophone: (enabled: boolean) => void;
}

export function WebSocketControls({
  socketStatus,
  micStatus,
  canUseRealtimeInput,
  textInput,
  setTextInput,
  connectSocket,
  disconnectSocket,
  clearConsole,
  sendText,
  toggleMicrophone,
}: WebSocketControlsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <>
      <div className={styles.actions}>
        <div className={styles.actionButtons}>
          <Button
            size="sm"
            kind="primary"
            onClick={connectSocket}
            disabled={socketStatus === 'connected' || socketStatus === 'connecting'}
          >
            {t('pages:test.websocket.actions.connect', 'Connect')}
          </Button>
          <Button
            size="sm"
            kind="secondary"
            onClick={disconnectSocket}
            disabled={socketStatus === 'disconnected'}
          >
            {t('pages:test.websocket.actions.disconnect', 'Disconnect')}
          </Button>
          <Button size="sm" kind="ghost" onClick={clearConsole}>
            {t('pages:test.websocket.actions.clear', 'Clear')}
          </Button>
        </div>
        <Toggle
          id="live-mic-toggle"
          className={styles.micToggle}
          size="sm"
          labelA={t('pages:test.websocket.form.micOff', 'Mic Off')}
          labelB={t('pages:test.websocket.form.micOn', 'Mic On')}
          labelText={t('pages:test.websocket.form.micToggle', 'Microphone Input')}
          toggled={micStatus !== 'off'}
          disabled={!canUseRealtimeInput || micStatus === 'starting'}
          onToggle={toggleMicrophone}
        />
      </div>

      <div className={styles.sendRow}>
        <TextInput
          id="live-text-input"
          labelText={t('pages:test.websocket.form.textInput', 'Realtime Text Input')}
          value={textInput}
          onChange={(event) => setTextInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              sendText();
            }
          }}
          placeholder={t('pages:test.websocket.form.textPlaceholder', 'Type a realtime prompt')}
          disabled={!canUseRealtimeInput}
        />
        <Button size="sm" kind="primary" onClick={sendText} disabled={!canUseRealtimeInput}>
          {t('pages:test.websocket.actions.send', 'Send')}
        </Button>
      </div>
    </>
  );
}
