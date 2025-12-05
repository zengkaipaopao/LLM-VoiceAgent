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
});

export type ConversationMessagePayload = {
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp?: string;
};

export async function fetchAppointments() {
  const response = await http.get<ApiAppointment[]>('/appointments');
  return response.data.map(mapRecord);
}

export async function createAppointmentFromConversation(messages: ConversationMessagePayload[]) {
  const response = await http.post<ApiAppointment>('/appointments', { messages });
  return mapRecord(response.data);
}
