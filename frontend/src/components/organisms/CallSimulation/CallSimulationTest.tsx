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
  UserMultiple,
  PhoneOff,
  CloseFilled,
} from '@carbon/icons-react';

import { ScenarioSelector, Scenario } from '../../molecules/Simulation/ScenarioSelector';
import { BatchTestControl } from '../../molecules/Simulation/BatchTestControl';
import styles from './CallSimulationTest.module.scss';

/**
 * Call Simulation Organism
 * 
 * 职责:
 * - 组装原子组件 (Molecules)
 * - 管理业务逻辑和数据状态
 * - 处理 API 调用
 */
interface CallSimulationTestProps {
  enableReviewer: boolean;
}

export const CallSimulationTest: React.FC<CallSimulationTestProps> = ({ enableReviewer }) => {
  const { t } = useTranslation(['pages']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);


  // 场景配置
  const scenarios: Scenario[] = [
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
  ];

  /**
   * API Handlers
   */
  const simulateCall = async (scenario: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await http.post(
        `/calls/simulate/incoming`,
        null,
        { 
          params: { 
            scenario,
            enable_reviewer: enableReviewer
          } 
        }
      );
      setResult({
        ...response.data.data,
        _message: t('pages:test.simulation.status.success')
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || t('pages:test.simulation.status.error', '模拟失败'));
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
        `/calls/simulate/batch`,
        null,
        { 
          params: { 
            count,
            enable_reviewer: enableReviewer
          } 
        }
      );
      const items = response.data.data || [];
      setResult({
        items,
        _message: t('pages:test.simulation.status.batchSuccess', { count: items.length })
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || t('pages:test.simulation.status.error', '批量模拟失败'));
    } finally {
      setLoading(false);
    }
  };

  const clearTestData = async () => {
    if (!confirm(t('pages:test.simulation.batch.confirmClear', '确定要清除所有测试数据吗?'))) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await http.delete(`/calls/simulate/clear-test-data`);
      setResult({
        ...response.data.data,
        _message: t('pages:test.simulation.status.clearSuccess', { count: response.data.data?.deleted_count || 0 })
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.message || t('pages:test.simulation.status.error', '清除失败'));
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
            onSelect={simulateCall}
            disabled={loading}
          />
        </Column>

        {/* 右侧工具区 - 批量测试 & 审查员 */}
        <Column lg={8} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            <BatchTestControl 
              onGenerate={simulateBatch}
              onClear={clearTestData}
              loading={loading}
              description={t('pages:test.simulation.batch.description', { 
                status: enableReviewer 
                  ? t('pages:test.simulation.batch.on') 
                  : t('pages:test.simulation.batch.off') 
              })}
            />
          </Stack>
        </Column>
      </Grid>

      {/* 状态反馈 */}
      {loading && <Loading description={t('pages:test.simulation.status.loading')} withOverlay={false} />}

      {error && (
        <InlineNotification
          kind="error"
          title={t('pages:test.simulation.status.error')}
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      )}

      {result && !error && (
        <InlineNotification
          kind="success"
          title={t('pages:test.simulation.status.success')}
          subtitle={result._message || 'Success'}
          onCloseButtonClick={() => setResult(null)}
          lowContrast
        />
      )}

      {/* 结果详情 */}
      {result && (
        <Tile>
          <Stack gap={4}>
            <h4 className="cds--label">{t('pages:test.simulation.response')}</h4>
            <CodeSnippet type="multi" feedback="已复制" wrapText>
              {JSON.stringify(result, null, 2)}
            </CodeSnippet>
          </Stack>
        </Tile>
      )}
    </div>
  );
};

export default CallSimulationTest;
