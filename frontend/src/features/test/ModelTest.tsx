import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  ComboBox,
  Grid,
  Column,
  InlineLoading,
  Stack,
  Tag,
  TextArea,
  Tile,
  Toggle,
} from '@carbon/react';
import { PageSubtitle } from '../../components/atoms/PageSubtitle';
import { PageTitle } from '../../components/atoms/PageTitle';
import { useModels } from '../../api/hooks';
import { sendChat } from '../../api/chat';
import { ModelInfo } from '../../types';

type HistoryItem = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  mode: 'text' | 'voice';
  model: string;
};

export function ModelTest() {
  const { data: models = [], isLoading: loadingModels, isError: modelError } = useModels();
  const [modelId, setModelId] = useState<string | null>(null);
  const [useVoice, setUseVoice] = useState(false);
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const canSend = useMemo(
    () => message.trim().length > 0 && !useVoice && !!modelId,
    [message, useVoice, modelId],
  );

  const modelOptions = models.map((m: ModelInfo) => ({
    id: m.id,
    label: `${m.name} (${m.provider})`,
  }));

  useEffect(() => {
    if (!modelId && models.length > 0) {
      setModelId(models[0].id);
    }
  }, [modelId, models]);

  const appendHistory = (items: HistoryItem[]) => setHistory((prev) => [...prev, ...items]);

  const handleSend = async () => {
    if (!canSend) return;
    setIsSending(true);
    const userMsg: HistoryItem = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message.trim(),
      mode: 'text',
      model: modelId ?? 'unknown',
    };
    appendHistory([userMsg]);
    try {
      const response = await sendChat(modelId ?? 'unknown', [{ role: 'user', content: message.trim() }]);
      const reply: HistoryItem = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.reply,
        mode: 'text',
        model: response.model_id,
      };
      appendHistory([reply]);
    } finally {
      setMessage('');
      setIsSending(false);
    }
  };

  const handleMockVoice = () => {
    const voiceMsg: HistoryItem = {
      id: crypto.randomUUID(),
      role: 'user',
      content: '（语音输入占位）',
      mode: 'voice',
      model: modelId ?? 'unknown',
    };
    appendHistory([voiceMsg]);
  };

  return (
    <section className="page-section">
      <PageTitle>模型测试</PageTitle>
      <PageSubtitle>选择模型并用文本/语音进行快速对话验证。</PageSubtitle>
      <Grid condensed fullWidth>
        <Column sm={4} md={4} lg={6}>
          <Tile>
            <Stack gap={4}>
              <ComboBox
                id="model-select"
                items={modelOptions}
                itemToString={(item) => (item ? item.label : '')}
                selectedItem={modelOptions.find((m) => m.id === modelId)}
                onChange={(data) => {
                  if (data.selectedItem) setModelId(data.selectedItem.id);
                }}
                titleText="选择模型"
                placeholder={loadingModels ? '模型加载中...' : '选择模型'}
                invalid={modelError}
                invalidText={modelError ? '模型列表获取失败' : undefined}
                disabled={loadingModels}
              />

              <Toggle
                id="voice-toggle"
                labelText="语音模式"
                toggled={useVoice}
                onToggle={(checked) => setUseVoice(checked)}
              />

              <TextArea
                id="message"
                labelText="输入文本"
                placeholder="输入要发送的内容"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                disabled={useVoice}
              />

              <Stack orientation="horizontal" gap={3}>
                <Button kind="primary" disabled={!canSend} onClick={handleSend}>
                  {isSending ? <InlineLoading description="发送中" /> : '发送文本'}
                </Button>
                <Button kind="ghost" disabled={!useVoice} onClick={handleMockVoice}>
                  模拟语音输入
                </Button>
                <Button kind="tertiary" onClick={() => setHistory([])}>
                  清空记录
                </Button>
              </Stack>
            </Stack>
          </Tile>
        </Column>

        <Column sm={4} md={4} lg={6}>
          <Tile>
            <Stack gap={3}>
              <PageSubtitle>对话记录</PageSubtitle>
              {history.length === 0 && <div>暂无记录</div>}
              {history.length > 0 && (
                <div className="chat-history">
                  {history.map((item) => (
                    <div
                      key={item.id}
                      className={`chat-bubble ${
                        item.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'
                      }`}
                    >
                      <div className="chat-meta">
                        <Tag type={item.role === 'user' ? 'blue' : 'green'}>{item.role}</Tag>
                        <Tag type="cool-gray">{item.model}</Tag>
                        <Tag type={item.mode === 'voice' ? 'purple' : 'gray'}>{item.mode}</Tag>
                      </div>
                      <div className="chat-content">{item.content}</div>
                    </div>
                  ))}
                </div>
              )}
            </Stack>
          </Tile>
        </Column>
      </Grid>
    </section>
  );
}
