import React from 'react';
import { Modal } from '@carbon/react';
import { useTranslation } from 'react-i18next';
import { DialogueViewer } from '../../molecules/DialogueViewer/DialogueViewer';
import styles from './AppointmentDetailModal.module.scss';
import { Appointment } from '../../../types/shared';
import { formatDateTime } from '../../../utils/formatters';
import { resolveAppointmentAmount } from '../../../utils/appointmentFields';
import { http } from '../../../api/http';

interface AppointmentDetailModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  appointment: Appointment | null;
}

export const AppointmentDetailModal: React.FC<AppointmentDetailModalProps> = ({
  open,
  onClose,
  onSuccess,
  appointment
}) => {
  const { t, i18n } = useTranslation(['pages', 'common']);
  const extracted = (appointment?.extracted_data || {}) as Record<string, any>;
  const resolvedAddress =
    appointment?.address ||
    extracted.pickup_address ||
    extracted.address ||
    '-';

  const resolvedAmount = resolveAppointmentAmount({
    amount: appointment?.amount,
    extractedData: extracted,
    summary: appointment?.summary,
    appointmentContent: extracted.appointment_content,
    rawMessages: appointment?.raw_messages,
  });

  return (
    <Modal
      open={open}
      onRequestClose={onClose}
      modalHeading={
        appointment
          ? t('pages:appointments.detailModal.headingWithName', {
              name: appointment.caller_name,
              defaultValue: 'Appointment Details: {{name}}',
            })
          : t('pages:appointments.detailModal.heading', 'Details')
      }
      onRequestSubmit={async () => {
          if (!appointment) return;
          try {
              await http.patch(`/appointments/${appointment.id}/handle`);
              onSuccess(); 
              onClose();
          } catch (e) {
              console.error(e);
          }
      }}
      primaryButtonText={t('pages:appointments.detailModal.markHandled', 'Mark handled')}
      secondaryButtonText={t('common:buttons.close')}
    >
      {appointment && (
        <div className={styles.container}>
          {/* ID Information - Upper Section */}
          <div className={styles.idSection}>
            <div>
              <strong>{t('pages:appointments.detailModal.appointmentEventId', 'Appointment Event ID')}:</strong>{' '}
              <span className={styles.mono}>{appointment.id}</span>
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.callId', 'Related Call ID')}:</strong>{' '}
              <span className={styles.mono}>{appointment.call_id || '-'}</span>
            </div>
          </div>
          
          <hr className={styles.divider} />
          
          <div className={styles.infoGrid}>
            <div>
              <strong>{t('pages:appointments.detailModal.timestamp', 'Created at')}:</strong>{' '}
              {appointment.timestamp ? formatDateTime(appointment.timestamp, i18n.language) : '-'}
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.appointmentTime', 'Appointment time')}:</strong>{' '}
              {appointment.appointment ? formatDateTime(appointment.appointment, i18n.language) : '-'}
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.callerName', 'Name')}:</strong> {appointment.caller_name}
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.company', 'Company')}:</strong> {appointment.company}
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.category', 'Category')}:</strong> {appointment.category}
            </div>
            <div>
              <strong>{t('pages:appointments.detailModal.amount', 'Amount')}:</strong> {resolvedAmount}
            </div>
          </div>
          <div>
            <strong>{t('pages:appointments.detailModal.address', 'Address')}:</strong> {resolvedAddress}
          </div>
          
          <hr className={styles.divider} />
          
          <div>
            <strong>{t('pages:appointments.detailModal.summary', 'Summary')}:</strong> {appointment.summary}
          </div>
          {appointment.extra_request && appointment.extra_request !== '-' && (
            <div>
              <strong>{t('pages:appointments.detailModal.extraRequest', 'Extra request')}:</strong>{' '}
              {appointment.extra_request}
            </div>
          )}
          
          {/* Reusable Dialogue Viewer Component */}
          <DialogueViewer rawMessages={appointment.raw_messages} />
        </div>
      )}
    </Modal>
  );
};
