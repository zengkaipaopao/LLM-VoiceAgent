import { http } from './http';
import { ReservationRecord } from '../types/shared';

type ApiAppointment = {
  id: string;
  timestamp: string;
  caller_name: string;
  company?: string;
  appointment: string;
  category?: string;
  amount?: string;
  address?: string;
  summary: string;
  extra_request?: string;
  raw_messages: string;
  operation: 'create' | 'update' | 'delete' | 'cancel';
};

const mapRecord = (record: ApiAppointment): ReservationRecord => ({
  id: record.id,
  timestamp: record.timestamp,
  callerName: record.caller_name,
  company: record.company || '',
  appointment: record.appointment,
  category: record.category || '',
  amount: record.amount || '',
  address: record.address || '',
  summary: record.summary,
  extraRequest: record.extra_request ?? '',
  rawMessages: record.raw_messages,
  operation: record.operation,
});

export async function fetchAppointments() {
  const response = await http.get('/appointments');
  return response.data.data.map(mapRecord);
}
