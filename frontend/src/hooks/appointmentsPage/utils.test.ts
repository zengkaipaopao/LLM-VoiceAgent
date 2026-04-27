import { describe, expect, it } from 'vitest';

import type { Appointment } from '../../types/shared';
import { mapAppointmentsToTableRows } from './utils';

function buildAppointment(overrides: Partial<Appointment>): Appointment {
  return {
    id: 'appt-1',
    timestamp: '2026-04-27T10:00:00+09:00',
    caller_name: '田中',
    company: 'EII',
    appointment: '2026-04-28T09:00:00+09:00',
    category: '粗大ごみ',
    amount: '3袋',
    address: 'Tokyo',
    summary: '回収予約',
    extra_request: '',
    raw_messages: [],
    operation: 'create',
    is_handled: false,
    extra_data: {},
    extracted_data: {},
    ...overrides,
  };
}

describe('mapAppointmentsToTableRows', () => {
  it('marks target appointment as linked-update when latest_operation_type is update', () => {
    const rows = mapAppointmentsToTableRows([
      buildAppointment({
        id: 'target-update',
        extra_data: { latest_operation_type: 'update' },
      }),
    ]);

    expect(rows[0]?.row_state).toBe('linked-update');
  });

  it('marks target appointment as linked-cancel when lifecycle_status is cancelled', () => {
    const rows = mapAppointmentsToTableRows([
      buildAppointment({
        id: 'target-cancel',
        extra_data: { lifecycle_status: 'cancelled' },
      }),
    ]);

    expect(rows[0]?.row_state).toBe('linked-cancel');
  });

  it('marks target appointment from linked operation event on the same page', () => {
    const rows = mapAppointmentsToTableRows([
      buildAppointment({
        id: 'target-create',
      }),
      buildAppointment({
        id: 'operation-event',
        operation: 'cancel',
        extra_data: { target_appointment_id: 'target-create' },
        extracted_data: { target_appointment_id: 'target-create' },
      }),
    ]);

    const targetRow = rows.find((row) => row.id === 'target-create');
    expect(targetRow?.row_state).toBe('linked-cancel');
  });
});
