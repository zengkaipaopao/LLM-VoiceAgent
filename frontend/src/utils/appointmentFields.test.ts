import { describe, expect, it } from 'vitest';

import { resolveAppointmentAmount } from './appointmentFields';

describe('resolveAppointmentAmount', () => {
  it('resolves amount from string estimated_weight_kg', () => {
    const amount = resolveAppointmentAmount({
      extractedData: {
        estimated_weight_kg: '3',
      },
    });

    expect(amount).toBe('3 kg');
  });

  it('resolves amount from raw_messages conversation fallback', () => {
    const amount = resolveAppointmentAmount({
      summary: 'Unified test session',
      rawMessages: {
        conversation: [
          { role: 'user', content: '粗大ゴミ３kg' },
          { role: 'assistant', content: '承知しました。' },
        ],
      },
    });

    expect(amount).toBe('３kg');
  });

  it('supports ton and cubic meter aliases from summary text', () => {
    const tonAmount = resolveAppointmentAmount({
      summary: '预计重量2t，尽快上门。',
    });
    const volumeAmount = resolveAppointmentAmount({
      summary: '大约8立方米',
    });
    const shortVolumeAmount = resolveAppointmentAmount({
      summary: '体积约3立方',
    });

    expect(tonAmount).toBe('2t');
    expect(volumeAmount).toBe('8立方米');
    expect(shortVolumeAmount).toBe('3立方');
  });

  it('does not parse ISO datetime text as amount', () => {
    const amount = resolveAppointmentAmount({
      rawMessages: {
        appointment_time: '2026-04-02T09:33:26+09:00',
      },
    });

    expect(amount).toBe('-');
  });
});
