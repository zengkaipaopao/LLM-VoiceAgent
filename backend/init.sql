-- ========================================
-- LLM Voice Agent 数据库初始化脚本
-- ========================================

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- 枚举类型定义
-- ========================================
DO $$ BEGIN
    CREATE TYPE call_direction AS ENUM ('inbound', 'outbound');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE call_status AS ENUM ('ringing', 'ongoing', 'completed', 'failed', 'no_answer', 'busy');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE handler_type AS ENUM ('ai', 'human', 'transferred');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ========================================
-- 通话记录表
-- ========================================
CREATE TABLE IF NOT EXISTS calls (
    -- 基础信息
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    direction call_direction NOT NULL,
    counterpart VARCHAR(50) NOT NULL,
    caller_name VARCHAR(100),
    
    -- 时间信息
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    answered_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    
    -- 状态信息
    status call_status NOT NULL DEFAULT 'ringing',
    handler_type handler_type DEFAULT 'ai',
    is_answered BOOLEAN DEFAULT FALSE,
    
    -- 内容信息
    summary TEXT,
    transcript TEXT,
    ai_confidence INTEGER CHECK (ai_confidence >= 0 AND ai_confidence <= 100),
    
    -- 转接信息
    transferred_at TIMESTAMP,
    transfer_reason VARCHAR(200),
    
    -- SIP信息
    sip_call_id VARCHAR(100),
    sip_from VARCHAR(100),
    sip_to VARCHAR(100),
    
    -- 关联信息
    prompt_id UUID,
    agent_id UUID,
    
    -- 元数据
    extra_data JSONB,
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_handler_type ON calls(handler_type);
CREATE INDEX IF NOT EXISTS idx_calls_counterpart ON calls(counterpart);
CREATE INDEX IF NOT EXISTS idx_calls_prompt_id ON calls(prompt_id);
CREATE INDEX IF NOT EXISTS idx_calls_sip_call_id ON calls(sip_call_id);

-- ========================================
-- Prompt模板表
-- ========================================
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),
    system_prompt TEXT NOT NULL,
    extraction_prompt TEXT,
    variables JSONB,
    example_conversations JSONB,
    extraction_schema JSONB,
    response_format VARCHAR(50) DEFAULT 'text',
    output_schema JSONB,
    llm_provider VARCHAR(50) DEFAULT 'gemini',
    llm_model VARCHAR(100) DEFAULT 'gemini-2.0-flash',
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2048,
    voice_provider VARCHAR(50),
    voice_id VARCHAR(100),
    voice_settings JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_prompt_templates_code ON prompt_templates(code);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_active ON prompt_templates(is_active);

-- ========================================
-- 预约记录表
-- ========================================
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID REFERENCES calls(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    caller_name VARCHAR(100) NOT NULL,
    company VARCHAR(200),
    appointment TIMESTAMP NOT NULL,
    category VARCHAR(50),
    amount VARCHAR(100),
    address TEXT,
    summary TEXT,
    extra_request TEXT,
    raw_messages JSONB,
    operation VARCHAR(10) CHECK (operation IN ('create', 'update', 'delete', 'cancel')),
    is_handled BOOLEAN NOT NULL DEFAULT FALSE,
    extra_data JSONB,
    prompt_id UUID,
    type_name VARCHAR(50),
    extracted_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_appointments_call_id ON appointments(call_id);
CREATE INDEX IF NOT EXISTS idx_appointments_timestamp ON appointments(timestamp);
CREATE INDEX IF NOT EXISTS idx_appointments_caller_name ON appointments(caller_name);
CREATE INDEX IF NOT EXISTS idx_appointments_prompt_id ON appointments(prompt_id);
CREATE INDEX IF NOT EXISTS idx_appointments_type_name ON appointments(type_name);

-- ========================================
-- Agent配置表
-- ========================================
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    llm_provider VARCHAR(20) NOT NULL CHECK (llm_provider IN ('openai', 'anthropic', 'azure', 'google')),
    voice VARCHAR(50),
    temperature DECIMAL(3, 2) CHECK (temperature >= 0 AND temperature <= 2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ========================================
-- 模型信息表
-- ========================================
CREATE TABLE IF NOT EXISTS models (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ========================================
-- 添加外键约束
-- ========================================
ALTER TABLE calls 
    ADD CONSTRAINT fk_calls_prompt 
    FOREIGN KEY (prompt_id) 
    REFERENCES prompt_templates(id) 
    ON DELETE SET NULL;

ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_prompt
    FOREIGN KEY (prompt_id)
    REFERENCES prompt_templates(id)
    ON DELETE SET NULL;

-- ========================================
-- 数据初始化
-- ========================================
-- 注意: 不在此处插入初始数据
-- 数据将通过后端应用程序动态管理和同步

-- ========================================
-- 创建更新时间触发器
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为所有表添加触发器
CREATE TRIGGER update_calls_updated_at BEFORE UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_prompt_templates_updated_at BEFORE UPDATE ON prompt_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_appointments_updated_at BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 完成
-- ========================================
COMMENT ON TABLE calls IS '通话记录表';
COMMENT ON TABLE prompt_templates IS 'Prompt模板表';
COMMENT ON TABLE appointments IS '预约记录表';
COMMENT ON TABLE agents IS 'Agent配置表';
COMMENT ON TABLE models IS '支持的LLM模型表';
