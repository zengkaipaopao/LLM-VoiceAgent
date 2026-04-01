import { Modal } from '@carbon/react';

import { CallLog } from '../../../types/shared';
import styles from './CallDetailsModal.module.scss';

type TranslateFn = (key: string) => string;

interface CallDetailsModalProps {
  open: boolean;
  onClose: () => void;
  selectedCall: CallLog | null;
  linkedAppointmentId: string | null;
  loadingLinkedAppointment: boolean;
  t: TranslateFn;
}

export function CallDetailsModal({
  open,
  onClose,
  selectedCall,
  linkedAppointmentId,
  loadingLinkedAppointment,
  t,
}: CallDetailsModalProps) {
  const modalHeading = selectedCall
    ? `${t('calls.detailModal.title')}: ${selectedCall.id}`
    : t('calls.detailModal.title');

  return (
    <Modal
      open={open}
      onRequestClose={onClose}
      modalHeading={modalHeading}
      passiveModal
    >
      {selectedCall && (
        <>
          <div className={styles.metaSection}>
            <div>
              <strong>Call ID:</strong> {selectedCall.id}
            </div>
            <div>
              <strong>Linked Appointment ID:</strong>{' '}
              {loadingLinkedAppointment ? 'Loading...' : linkedAppointmentId || '-'}
            </div>
          </div>
          <pre className={styles.rawPayload}>{JSON.stringify(selectedCall, null, 2)}</pre>
        </>
      )}
    </Modal>
  );
}
