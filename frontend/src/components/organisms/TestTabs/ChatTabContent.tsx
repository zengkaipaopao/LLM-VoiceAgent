import React from 'react';
import { ChatInterface } from '../../organisms/ChatInterface';

/**
 * ChatTabContent - LLM 对话测试 Tab 内容
 * 
 * 功能:
 * - 提供 LLM 对话测试界面
 * - 支持流式响应
 * - 支持多种 Prompt 模板
 */
export const ChatTabContent: React.FC = () => {
  return (
    <div style={{ padding: 'var(--cds-spacing-05)' }}>
      <ChatInterface 
        defaultProvider="gemini"
        defaultTemplate="general_appointment"
      />
    </div>
  );
};
