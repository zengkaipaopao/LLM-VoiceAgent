import { http } from './http';
import { ReservationRecord } from '../types';

type ApiAppointment = {
  id: string;
  timestamp: string;
  caller_name: string;
  company: string;
  appointment: string;
  category: string;
  amount: string;
  address: string;
  summary: string;
  raw_messages: string;
  operation: 'create' | 'update' | 'delete';
};

const mapRecord = (record: ApiAppointment): ReservationRecord => ({
  id: record.id,
  timestamp: record.timestamp,
  callerName: record.caller_name,
  company: record.company,
  appointment: record.appointment,
  category: record.category,
  amount: record.amount,
  address: record.address,
  summary: record.summary,
  rawMessages: record.raw_messages,
  operation: record.operation,
});

export type AppointmentRecordPayload = {
  timestamp: string;
  callerName: string;
  company: string;
  appointment: string;
  category: string;
  amount: string;
  address: string;
  summary: string;
  rawMessages: string;
  operation: 'create' | 'update' | 'delete';
};

export async function fetchAppointments() {
  const response = await http.get<ApiAppointment[]>('/appointments');
  return response.data.map(mapRecord);
}

export async function submitAppointmentRecord(payload: AppointmentRecordPayload) {
  const response = await http.post<ApiAppointment>('/appointments', {
    timestamp: payload.timestamp,
    caller_name: payload.callerName,
    company: payload.company,
    appointment: payload.appointment,
    category: payload.category,
    amount: payload.amount,
    address: payload.address,
    summary: payload.summary,
    raw_messages: payload.rawMessages,
    operation: payload.operation,
  });
  return mapRecord(response.data);
}
