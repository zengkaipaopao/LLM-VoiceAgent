import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { http } from '../../../api/http';
import {
  InlineNotification,
  CodeSnippet,
  Loading,
  Tile,
  Grid,
  Column,
  Stack,
} from '@carbon/react';
import {
  CheckmarkFilled,
  WarningFilled,
  Time,
  ErrorFilled,
} from '@carbon/icons-react';

import { ScenarioSelector, Scenario } from '../../molecules/Simulation/ScenarioSelector';
import { BatchTestControl } from '../../molecules/Simulation/BatchTestControl';
import styles from './AppointmentSimulationTest.module.scss';

/**
 * Appointment Simulation Organism
 */
export const AppointmentSimulationTest: React.FC = () => {
  const { t } = useTranslation(['pages']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // 临时使用硬编码的翻译，后续可以添加到 locales
  const scenarios: Scenario[] = [
    {
      id: 'new',
      title: '新预约',
      description: '模拟新用户的预约请求',
      icon: CheckmarkFilled,
      iconColor: '#24a148',
    },
    {
      id: 'update',
      title: '预约变更',
      description: '模拟修改已有预约的时间或内容',
      icon: Time,
      iconColor: '#f1c21b',
    },
    {
      id: 'cancel',
      title: '取消预约',
      description: '模拟用户取消预约',
      icon: ErrorFilled,
      iconColor: '#da1e28',
    },
  ];

  /**
   * API Handlers
   */
  const simulateAppointment = async (scenario: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await http.post(
        '/appointments/simulate/incoming',
        null,
        { 
          params: { scenario } 
        }
      );
      setResult({
        ...response.data.data,
        _message: 'Appointment simulated successfully'
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const simulateBatch = async (count: number) => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await http.post(
        '/appointments/simulate/batch',
        null,
        { 
          params: { count } 
        }
      );
      const items = response.data.data || [];
      setResult({
        items,
        _message: `Batch ${items.length} appointments simulated successfully`
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Batch simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const clearTestData = async () => {
    if (!confirm('Are you sure you want to clear all simulated appointment data?')) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await http.delete('/appointments/simulate/clear-test-data');
      setResult({
        ...response.data.data,
        _message: `Cleared ${response.data.data?.deleted_count || 0} test appointments`
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Clear failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <Grid narrow className={styles.gridContainer}>
        {/* 左侧主要操作区 - 场景选择 */}
        <Column lg={8} md={8} sm={4} className={styles.mainColumn}>
          <ScenarioSelector 
            scenarios={scenarios}
            onSelect={simulateAppointment}
            disabled={loading}
          />
        </Column>

        {/* 右侧工具区 - 批量测试 */}
        <Column lg={8} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <BatchTestControl 
              onGenerate={simulateBatch}
              onClear={clearTestData}
              loading={loading}
              title="Batch Simuation"
              description="Generate multiple appointments at once."
              countLabel="Count"
              generateButtonText="Generate Appointments"
              clearButtonText="Clear Simulated Data"
            />
          </Stack>
        </Column>
      </Grid>

      {/* 状态反馈 */}
      {loading && <Loading description="Loading..." withOverlay={false} />}

      {error && (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      )}

      {result && !error && (
        <InlineNotification
          kind="success"
          title="Success"
          subtitle={result._message || result.message || 'Success'}
          onCloseButtonClick={() => setResult(null)}
          lowContrast
        />
      )}

      {/* 结果详情 */}
      {result && (
        <Tile>
          <Stack gap={4}>
            <h4 className="cds--label">Response Data</h4>
            <CodeSnippet type="multi" feedback="Copied" wrapText>
              {JSON.stringify(result, null, 2)}
            </CodeSnippet>
          </Stack>
        </Tile>
      )}
    </div>
  );
};
