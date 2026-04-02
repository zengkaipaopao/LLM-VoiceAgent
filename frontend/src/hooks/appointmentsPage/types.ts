import { Appointment } from '../../types/shared';

export type DynamicSchemaField = {
  name: string;
  label?: string;
};

export type AppointmentListPayload = {
  data?: Appointment[];
  meta?: {
    pagination?: {
      total_items?: number;
    };
  };
};

export type AppointmentTableRow = {
  id: string;
  timestamp: string;
  appointment: string;
  operation: string;
  row_state?: 'default' | 'linked-update' | 'linked-cancel';
  is_handled: boolean | undefined;
  caller_name: string;
  company: string;
  category: string;
  amount: string | number | null;
  address: string;
  summary: string;
  extra_request: string;
  raw: Appointment;
  [key: string]: unknown;
};
