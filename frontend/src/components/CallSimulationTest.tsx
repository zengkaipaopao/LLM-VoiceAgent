import React, { useState } from 'react';
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
} from '@carbon/icons-react';

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
export const CallSimulationTest: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

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
        { params: { scenario } }
      );
      
      setResult(response.data);
      console.log('✅ 模拟通话成功:', response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || '模拟失败');
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
        { params: { count } }
      );
      
      setResult(response.data);
      console.log(`✅ 批量模拟${count}个通话成功:`, response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || '批量模拟失败');
      console.error('❌ 批量模拟失败:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 清除测试数据
   */
  const clearTestData = async () => {
    if (!confirm('确定要清除所有测试数据吗?')) return;
    
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
      setError(err.response?.data?.message || '清除失败');
      console.error('❌ 清除失败:', err);
    } finally {
      setLoading(false);
    }
  };

  // 场景配置
  const scenarios = [
    {
      id: 'ai_handled',
      title: 'AI成功处理',
      description: '模拟AI完整处理来电',
      icon: CheckmarkFilled,
      iconColor: '#24a148',
    },
    {
      id: 'transferred',
      title: '转人工',
      description: '模拟AI转接人工客服',
      icon: UserMultiple,
      iconColor: '#f1c21b',
    },
    {
      id: 'no_answer',
      title: '未接听',
      description: '模拟来电无人接听',
      icon: PhoneOff,
      iconColor: '#8d8d8d',
    },
    {
      id: 'failed',
      title: '呼叫失败',
      description: '模拟通话失败场景',
      icon: CloseFilled,
      iconColor: '#da1e28',
    },
  ];

  return (
    <Stack gap={6}>
      {/* 场景选择卡片 */}
      <div>
        <h4 className="cds--label" style={{ marginBottom: '1rem' }}>
          选择测试场景
        </h4>
        <Grid narrow>
          {scenarios.map((scenario) => (
            <Column key={scenario.id} lg={4} md={4} sm={2}>
              <ClickableTile
                onClick={() => simulateCall(scenario.id)}
                disabled={loading}
                style={{ height: '100%' }}
              >
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '0.5rem',
                  height: '100%',
                }}>
                  <scenario.icon 
                    size={32} 
                    style={{ color: scenario.iconColor }} 
                  />
                  <div>
                    <h5 className="cds--type-heading-compact-01" style={{ marginBottom: '0.25rem' }}>
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
      </div>

      {/* 批量操作 */}
      <Tile>
        <Stack gap={4}>
          <div>
            <h4 className="cds--label">批量测试</h4>
            <p className="cds--label-description">
              快速生成多条测试数据用于开发调试
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
                  style={{ width: '100%', maxWidth: '100%' }}
                >
                  生成 10 条测试数据
                </Button>
                
                <Button
                  kind="secondary"
                  onClick={() => simulateBatch(50)}
                  disabled={loading}
                  renderIcon={Renew}
                  style={{ width: '100%', maxWidth: '100%' }}
                >
                  生成 50 条测试数据
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
                  style={{ width: '100%', maxWidth: '100%' }}
                >
                  清除所有测试数据
                </Button>
              </Stack>
            </Column>
          </Grid>
        </Stack>
      </Tile>

      {/* Loading状态 */}
      {loading && <Loading description="处理中..." withOverlay={false} />}

      {/* 错误提示 */}
      {error && (
        <InlineNotification
          kind="error"
          title="操作失败"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      )}

      {/* 成功提示 */}
      {result && !error && (
        <InlineNotification
          kind="success"
          title="操作成功"
          subtitle={result.message}
          onCloseButtonClick={() => setResult(null)}
          lowContrast
        />
      )}

      {/* 结果详情 */}
      {result && (
        <Tile>
          <Stack gap={4}>
            <h4 className="cds--label">响应详情</h4>
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

      {/* 使用说明 */}
      <InlineNotification
        kind="info"
        title="开发说明"
        subtitle=""
        lowContrast
        hideCloseButton
      >
        <Stack gap={3} style={{ marginTop: '0.5rem' }}>
          <p className="cds--body-compact-01">
            <strong>当前阶段:</strong> 点击卡片模拟通话,测试后端API
          </p>
          <p className="cds--body-compact-01">
            <strong>生产环境:</strong> 将替换为真实SIP事件触发 (INVITE, BYE等)
          </p>
          <p className="cds--body-compact-01">
            <strong>测试数据:</strong> 所有模拟数据标记为 <code>extra_data.simulation = true</code>,可随时清除
          </p>
        </Stack>
      </InlineNotification>
    </Stack>
  );
};

export default CallSimulationTest;
