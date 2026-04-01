import { Tag } from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { MicStatus, SocketStatus } from '../../../../hooks/useLiveWebSocketConsole';
import styles from '../WebSocketTabContent.module.scss';

interface WebSocketStatusHeaderProps {
  socketStatus: SocketStatus;
  micStatus: MicStatus;
}

function resolveSocketTagType(status: SocketStatus): 'green' | 'teal' | 'red' | 'cool-gray' {
  if (status === 'connected') return 'green';
  if (status === 'connecting') return 'teal';
  if (status === 'error') return 'red';
  return 'cool-gray';
}

function resolveMicTagType(status: MicStatus): 'green' | 'teal' | 'cool-gray' {
  if (status === 'on') return 'green';
  if (status === 'starting') return 'teal';
  return 'cool-gray';
}

export function WebSocketStatusHeader({ socketStatus, micStatus }: WebSocketStatusHeaderProps) {
  const { t } = useTranslation(['pages']);
  const statusTagType = resolveSocketTagType(socketStatus);
  const micTagType = resolveMicTagType(micStatus);

  return (
    <div className={styles.header}>
      <div>
        <h3 className="cds--heading-03">
          {t('pages:test.websocket.title', 'Gemini Live WebSocket Console')}
        </h3>
        <p className={styles.description}>
          {t(
            'pages:test.websocket.description',
            'Connect to backend live gateway, stream mic audio, and inspect transcripts.'
          )}
        </p>
      </div>
      <div className={styles.statusTags}>
        <Tag type={statusTagType}>{`Socket: ${socketStatus}`}</Tag>
        <Tag type={micTagType}>{`Mic: ${micStatus}`}</Tag>
      </div>
    </div>
  );
}
