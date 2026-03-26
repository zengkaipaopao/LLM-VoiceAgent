import React from 'react';
import { Modal } from '@carbon/react';
import { DialogueViewer } from '../../molecules/DialogueViewer/DialogueViewer';
import styles from './AppointmentDetailModal.module.scss';
import { Appointment } from '../../../types/shared';
import { formatJapaneseDate } from '../../../utils/formatters';
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
  });

  return (
    <Modal
      open={open}
      onRequestClose={onClose}
      modalHeading={appointment ? `预约详情: ${appointment.caller_name}` : '详情'}
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
      primaryButtonText="对应完毕"
      secondaryButtonText="关闭"
    >
      {appointment && (
        <div className={styles.container}>
          {/* ID Information - Upper Section */}
          <div className={styles.idSection}>
            <div>
              <strong>预约事件ID:</strong> <span className={styles.mono}>{appointment.id}</span>
            </div>
            <div>
              <strong>关联通话ID:</strong> <span className={styles.mono}>{appointment.call_id || '-'}</span>
            </div>
          </div>
          
          <hr className={styles.divider} />
          
          <div className={styles.infoGrid}>
            <div><strong>预约时间:</strong> {formatJapaneseDate(appointment.timestamp)}</div>
            <div><strong>希望回收时间:</strong> {formatJapaneseDate(appointment.appointment)}</div>
            <div><strong>姓名:</strong> {appointment.caller_name}</div>
            <div><strong>公司:</strong> {appointment.company}</div>
            <div><strong>类别:</strong> {appointment.category}</div>
            <div><strong>数量:</strong> {resolvedAmount}</div>
          </div>
          <div><strong>地址:</strong> {resolvedAddress}</div>
          
          <hr className={styles.divider} />
          
          <div><strong>摘要:</strong> {appointment.summary}</div>
          {appointment.extra_request && appointment.extra_request !== '-' && (
            <div><strong>额外请求:</strong> {appointment.extra_request}</div>
          )}
          
          {/* Reusable Dialogue Viewer Component */}
          <DialogueViewer rawMessages={appointment.raw_messages} />
        </div>
      )}
    </Modal>
  );
};
