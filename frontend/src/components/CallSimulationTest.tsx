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
  NumberInput,
  ButtonSet,
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
  const [batchCount, setBatchCount] = useState(10);
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
    <div className={styles.container}>
      <Grid narrow className={styles.gridContainer}>
        {/* 左侧主要操作区 - 场景选择 */}
        <Column lg={8} md={8} sm={4} className={styles.mainColumn}>
          <Stack gap={6}>
            <section>
              <h4 className={`cds--heading-03 ${styles.sectionTitle}`}>
                {t('pages:test.simulation.scenarios.title')}
              </h4>
              <p className={`cds--body-01 ${styles.sectionDescription}`}>
                {t('pages:test.simulation.scenarios.description', 'Select a scenario to simulate an incoming call.')}
              </p>
              
              <div className={styles.scenarioGrid}>
                {scenarios.map((scenario) => (
                  <ClickableTile
                    key={scenario.id}
                    onClick={() => simulateCall(scenario.id)}
                    disabled={loading}
                    className={styles.scenarioTile}
                  >
                    <div className={styles.tileContent}>
                      <div className={styles.tileIcon}>
                        <scenario.icon 
                          size={24} 
                          style={{ color: scenario.iconColor }} 
                        />
                      </div>
                      <div>
                        <h5 className={`cds--heading-compact-01 ${styles.iconWithTitle}`}>
                          {scenario.title}
                        </h5>
                        <p className="cds--body-compact-01 cds--text--secondary">
                          {scenario.description}
                        </p>
                      </div>
                    </div>
                  </ClickableTile>
                ))}
              </div>
            </section>
          </Stack>
        </Column>

        {/* 右侧工具区 - 批量测试 & 审查员 */}
        <Column lg={8} md={8} sm={4} className={styles.sideColumn}>
          <Stack gap={6}>
            {/* 批量操作 Panel */}
            <Tile className={styles.toolTile}>
              <Stack gap={6}>
                <div>
                  <h4 className="cds--heading-compact-02">{t('pages:test.simulation.batch.title')}</h4>
                  <p className="cds--body-compact-01 cds--text--secondary">
                    {t('pages:test.simulation.batch.description', { 
                      status: enableReviewer 
                        ? t('pages:test.simulation.batch.on') 
                        : t('pages:test.simulation.batch.off') 
                    })}
                  </p>
                </div>
            
            {/* 主要操作区 */}
            <div className={styles.batchControls}>
              <NumberInput
                id="batch-count"
                label={t('pages:test.simulation.batch.countLabel', '生成数量')}
                min={1}
                max={1000}
                value={batchCount}
                onChange={(e: any) => setBatchCount(e.imaginaryTarget.value)}
                invalidText={t('pages:test.simulation.batch.invalidCount', '请输入1-1000之间的数字')}
                disabled={loading}
              />
              <Button
                kind="primary"
                onClick={() => simulateBatch(batchCount)}
                disabled={loading}
                renderIcon={Renew}
                className={styles.generateButton}
              >
                {t('pages:test.simulation.batch.generate', '生成测试数据')}
              </Button>
            </div>

            {/* 快捷选项 */}
            <div className={styles.quickActions}>
              <span className="cds--label">{t('pages:test.simulation.batch.quickOptions', '快捷选项:')}</span>
              <ButtonSet>
                <Button 
                  size="sm" 
                  kind="ghost" 
                  onClick={() => setBatchCount(10)}
                  disabled={loading}
                >
                  10
                </Button>
                <Button 
                  size="sm" 
                  kind="ghost" 
                  onClick={() => setBatchCount(50)}
                  disabled={loading}
                >
                  50
                </Button>
                <Button 
                  size="sm" 
                  kind="ghost" 
                  onClick={() => setBatchCount(100)}
                  disabled={loading}
                >
                  100
                </Button>
              </ButtonSet>
            </div>

                {/* 危险操作 */}
                <Button
                  kind="danger--tertiary"
                  onClick={clearTestData}
                  disabled={loading}
                  renderIcon={TrashCan}
                >
                  {t('pages:test.simulation.batch.clear')}
                </Button>
              </Stack>
            </Tile>
          </Stack>
        </Column>
      </Grid>

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
    </div>
  );


};

export default CallSimulationTest;
