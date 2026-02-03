import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import {
  Button,
  InlineNotification,
  CodeSnippet,
  Loading,
  Tile,
  ClickableTile,
  Grid,
  Column,
  Stack,

} from '@carbon/react';
import {
  CheckmarkFilled,
  WarningFilled,
  ErrorFilled,
  Renew,
  TrashCan,
  Phone,
  UserMultiple,
  PhoneOff,
  CloseFilled,
  WatsonHealthAiStatus,
} from '@carbon/icons-react';
import styles from './CallSimulationTest.module.css';

/**
 * Call Simulation Test Component
 * 
 * 完全遵循 Carbon Design System 设计原则:
 * - 使用 ClickableTile 提供交互式卡片
 * - 使用 Stack 组件管理垂直间距
 * - 使用 Grid 系统实现响应式布局
 * - 清晰的视觉层级和信息架构
 * - 符合 Carbon 的间距和颜色规范
 * 
 * 将来替换为真实的SIP事件触发
 */
interface CallSimulationTestProps {
  enableReviewer: boolean;
}

export const CallSimulationTest: React.FC<CallSimulationTestProps> = ({ enableReviewer }) => {
  const { t } = useTranslation(['pages']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  // Removed local enableReviewer state as it is now passed via props

  const API_BASE = 'http://localhost:8000/api/v1';

  /**
   * 模拟单个来电
   */
  const simulateCall = async (scenario: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await axios.post(
        `${API_BASE}/calls/simulate/incoming`,
        null,
        { 
          params: { 
            scenario,
            enable_reviewer: enableReviewer
          } 
        }
      );
      
      setResult(response.data);
      console.log('✅ 模拟通话成功:', response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || t('pages:test.simulation.status.error', '模拟失败'));
      console.error('❌ 模拟失败:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 批量模拟通话
   */
  const simulateBatch = async (count: number) => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await axios.post(
        `${API_BASE}/calls/simulate/batch`,
        null,
        { 
          params: { 
            count,
            enable_reviewer: enableReviewer
          } 
        }
      );
      
      setResult(response.data);
      console.log(`✅ 批量模拟${count}个通话成功:`, response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || t('pages:test.simulation.status.error', '批量模拟失败'));
      console.error('❌ 批量模拟失败:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 清除测试数据
   */
  const clearTestData = async () => {
    if (!confirm(t('pages:test.simulation.batch.confirmClear', '确定要清除所有测试数据吗?'))) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await axios.delete(
        `${API_BASE}/calls/simulate/clear-test-data`
      );
      
      setResult(response.data);
      console.log('✅ 清除测试数据成功:', response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || t('pages:test.simulation.status.error', '清除失败'));
      console.error('❌ 清除失败:', err);
    } finally {
      setLoading(false);
    }
  };

  // 场景配置
  const scenarios = [
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

  return (
    <Stack gap={6}>
      <Stack gap={6}>
        {/* 场景选择卡片 */}
        <Tile>
          <h4 className={`cds--label ${styles.label}`}>
            {t('pages:test.simulation.scenarios.title')}
          </h4>
          <Grid narrow>
            {scenarios.map((scenario) => (
              <Column key={scenario.id} lg={4} md={4} sm={2}>
                <ClickableTile
                  onClick={() => simulateCall(scenario.id)}
                  disabled={loading}
                  className={styles.tile}
                >
                  <div className={styles.tileContent}>
                    <scenario.icon 
                      size={32} 
                      style={{ color: scenario.iconColor }} 
                    />
                    <div>
                      <h5 className={`cds--type-heading-compact-01 ${styles.iconWithTitle}`}>
                        {scenario.title}
                      </h5>
                      <p className="cds--label-description">
                        {scenario.description}
                      </p>
                    </div>
                  </div>
                </ClickableTile>
              </Column>
            ))}
          </Grid>
        </Tile>

        {/* 批量操作 */}
        <Tile>
          <Stack gap={4}>
            <div>
              <h4 className="cds--label">{t('pages:test.simulation.batch.title')}</h4>
              <p className="cds--label-description">
                {t('pages:test.simulation.batch.description', { 
                  status: enableReviewer 
                    ? t('pages:test.simulation.batch.on') 
                    : t('pages:test.simulation.batch.off') 
                })}
              </p>
            </div>
            
            <Grid narrow>
              <Column lg={8} md={4} sm={2}>
                <Stack gap={3}>
                  <Button
                    kind="secondary"
                    onClick={() => simulateBatch(10)}
                    disabled={loading}
                    renderIcon={Renew}
                    className={styles.actionButton}
                  >
                    {t('pages:test.simulation.batch.generate10')}
                  </Button>
                  
                  <Button
                    kind="secondary"
                    onClick={() => simulateBatch(50)}
                    disabled={loading}
                    renderIcon={Renew}
                    className={styles.actionButton}
                  >
                    {t('pages:test.simulation.batch.generate50')}
                  </Button>
                </Stack>
              </Column>
              
              <Column lg={8} md={4} sm={2}>
                <Stack gap={3}>
                  <Button
                    kind="danger"
                    onClick={clearTestData}
                    disabled={loading}
                    renderIcon={TrashCan}
                    className={styles.actionButton}
                  >
                   {t('pages:test.simulation.batch.clear')}
                  </Button>
                </Stack>
              </Column>
            </Grid>
          </Stack>
        </Tile>
      </Stack>

      {/* Loading状态 */}
      {loading && <Loading description={t('pages:test.simulation.status.loading')} withOverlay={false} />}

      {/* 错误提示 */}
      {error && (
        <InlineNotification
          kind="error"
          title={t('pages:test.simulation.status.error')}
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      )}

      {/* 成功提示 */}
      {result && !error && (
        <InlineNotification
          kind="success"
          title={t('pages:test.simulation.status.success')}
          subtitle={result.message}
          onCloseButtonClick={() => setResult(null)}
          lowContrast
        />
      )}

      {/* 结果详情 */}
      {result && (
        <Tile>
          <Stack gap={4}>
            <h4 className="cds--label">{t('pages:test.simulation.response')}</h4>
            <CodeSnippet 
              type="multi" 
              feedback="已复制"
              wrapText
            >
              {JSON.stringify(result, null, 2)}
            </CodeSnippet>
          </Stack>
        </Tile>
      )}
    </Stack>
  );


};

export default CallSimulationTest;
