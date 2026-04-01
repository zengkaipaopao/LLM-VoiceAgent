import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckmarkFilled,
  ErrorFilled,
  Time,
} from '@carbon/icons-react';

import { http } from '../api/http';
import { Scenario } from '../components/molecules/Simulation/ScenarioSelector';

type SimulationResult = Record<string, unknown> | null;

function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown; message?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === 'string' && detail.trim() !== '') {
      return detail;
    }
    const message = response?.data?.message;
    if (typeof message === 'string' && message.trim() !== '') {
      return message;
    }
  }

  return fallback;
}

function mergeResult(payload: unknown, message: string): Record<string, unknown> {
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    return {
      ...(payload as Record<string, unknown>),
      _message: message,
    };
  }
  return {
    data: payload,
    _message: message,
  };
}

export interface UseAppointmentSimulationTestResult {
  scenarios: Scenario[];
  loading: boolean;
  result: SimulationResult;
  setResult: (value: SimulationResult) => void;
  error: string | null;
  setError: (value: string | null) => void;
  simulateAppointment: (scenario: string) => Promise<void>;
  simulateBatch: (count: number) => Promise<void>;
  clearTestData: () => Promise<void>;
}

export function useAppointmentSimulationTest(): UseAppointmentSimulationTestResult {
  const { t } = useTranslation(['pages']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult>(null);
  const [error, setError] = useState<string | null>(null);

  const scenarios = useMemo<Scenario[]>(
    () => [
      {
        id: 'new',
        title: t('pages:test.appointment.scenarios.new.title', '新预约'),
        description: t('pages:test.appointment.scenarios.new.description', '模拟新用户的预约请求'),
        icon: CheckmarkFilled,
        iconColor: '#24a148',
      },
      {
        id: 'update',
        title: t('pages:test.appointment.scenarios.update.title', '预约变更'),
        description: t('pages:test.appointment.scenarios.update.description', '模拟修改已有预约的时间或内容'),
        icon: Time,
        iconColor: '#f1c21b',
      },
      {
        id: 'cancel',
        title: t('pages:test.appointment.scenarios.cancel.title', '取消预约'),
        description: t('pages:test.appointment.scenarios.cancel.description', '模拟用户取消预约'),
        icon: ErrorFilled,
        iconColor: '#da1e28',
      },
    ],
    [t]
  );

  const simulateAppointment = async (scenario: string) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.post('/appointments/simulate/incoming', null, {
        params: { scenario },
      });
      setResult(
        mergeResult(
          response.data?.data,
          t('pages:test.appointment.status.success', 'Appointment simulated successfully')
        )
      );
    } catch (requestError) {
      setError(
        extractApiErrorMessage(requestError, t('pages:test.appointment.status.error', 'Simulation failed'))
      );
    } finally {
      setLoading(false);
    }
  };

  const simulateBatch = async (count: number) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.post('/appointments/simulate/batch', null, {
        params: { count },
      });
      const items = Array.isArray(response.data?.data) ? response.data.data : [];
      setResult(
        mergeResult(
          { items },
          t('pages:test.appointment.status.batchSuccess', `Batch ${items.length} appointments simulated successfully`)
        )
      );
    } catch (requestError) {
      setError(
        extractApiErrorMessage(requestError, t('pages:test.appointment.status.batchError', 'Batch simulation failed'))
      );
    } finally {
      setLoading(false);
    }
  };

  const clearTestData = async () => {
    if (
      !window.confirm(
        t(
          'pages:test.appointment.batch.confirmClear',
          'Are you sure you want to clear all simulated appointment data?'
        )
      )
    ) {
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.delete('/appointments/simulate/clear-test-data');
      const payload = response.data?.data as { deleted_count?: number } | undefined;
      setResult(
        mergeResult(
          payload,
          t(
            'pages:test.appointment.status.clearSuccess',
            `Cleared ${payload?.deleted_count || 0} test appointments`
          )
        )
      );
    } catch (requestError) {
      setError(extractApiErrorMessage(requestError, t('pages:test.appointment.status.clearError', 'Clear failed')));
    } finally {
      setLoading(false);
    }
  };

  return {
    scenarios,
    loading,
    result,
    setResult,
    error,
    setError,
    simulateAppointment,
    simulateBatch,
    clearTestData,
  };
}
