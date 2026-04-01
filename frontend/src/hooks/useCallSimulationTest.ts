import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckmarkFilled,
  CloseFilled,
  PhoneOff,
  UserMultiple,
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

export interface UseCallSimulationTestResult {
  scenarios: Scenario[];
  loading: boolean;
  result: SimulationResult;
  setResult: (value: SimulationResult) => void;
  error: string | null;
  setError: (value: string | null) => void;
  simulateCall: (scenario: string) => Promise<void>;
  simulateBatch: (count: number) => Promise<void>;
  clearTestData: () => Promise<void>;
}

export function useCallSimulationTest(enableReviewer: boolean): UseCallSimulationTestResult {
  const { t } = useTranslation(['pages']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult>(null);
  const [error, setError] = useState<string | null>(null);

  const scenarios = useMemo<Scenario[]>(
    () => [
      {
        id: 'ai_handled',
        title: t('pages:test.simulation.scenarios.ai_handled.title'),
        description: t('pages:test.simulation.scenarios.ai_handled.description'),
        icon: CheckmarkFilled,
        iconColor: '#24a148',
      },
      {
        id: 'transferred',
        title: t('pages:test.simulation.scenarios.transferred.title'),
        description: t('pages:test.simulation.scenarios.transferred.description'),
        icon: UserMultiple,
        iconColor: '#f1c21b',
      },
      {
        id: 'no_answer',
        title: t('pages:test.simulation.scenarios.no_answer.title'),
        description: t('pages:test.simulation.scenarios.no_answer.description'),
        icon: PhoneOff,
        iconColor: '#8d8d8d',
      },
      {
        id: 'failed',
        title: t('pages:test.simulation.scenarios.failed.title'),
        description: t('pages:test.simulation.scenarios.failed.description'),
        icon: CloseFilled,
        iconColor: '#da1e28',
      },
    ],
    [t]
  );

  const simulateCall = async (scenario: string) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.post('/calls/simulate/incoming', null, {
        params: {
          scenario,
          enable_reviewer: enableReviewer,
        },
      });
      const payload = response.data?.data;
      setResult(mergeResult(payload, t('pages:test.simulation.status.success')));
    } catch (requestError) {
      setError(extractApiErrorMessage(requestError, t('pages:test.simulation.status.error', '模拟失败')));
    } finally {
      setLoading(false);
    }
  };

  const simulateBatch = async (count: number) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.post('/calls/simulate/batch', null, {
        params: {
          count,
          enable_reviewer: enableReviewer,
        },
      });
      const items = Array.isArray(response.data?.data) ? response.data.data : [];
      setResult(
        mergeResult(
          { items },
          t('pages:test.simulation.status.batchSuccess', {
            count: items.length,
          })
        )
      );
    } catch (requestError) {
      setError(extractApiErrorMessage(requestError, t('pages:test.simulation.status.error', '批量模拟失败')));
    } finally {
      setLoading(false);
    }
  };

  const clearTestData = async () => {
    if (!window.confirm(t('pages:test.simulation.batch.confirmClear', '确定要清除所有测试数据吗?'))) {
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await http.delete('/calls/simulate/clear-test-data');
      const payload = response.data?.data as { deleted_count?: number } | undefined;
      setResult(
        mergeResult(
          payload,
          t('pages:test.simulation.status.clearSuccess', {
            count: payload?.deleted_count || 0,
          })
        )
      );
    } catch (requestError) {
      setError(extractApiErrorMessage(requestError, t('pages:test.simulation.status.error', '清除失败')));
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
    simulateCall,
    simulateBatch,
    clearTestData,
  };
}
