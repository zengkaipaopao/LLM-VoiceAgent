-- ==================== LLM Chat System Database Migration ====================
-- 
-- This migration adds support for LLM chat functionality with prompt templates
-- 
-- Tables created:
-- 1. prompt_templates - Stores prompt templates for different scenarios
--
-- ===============================================================================

-- Create prompt_templates table
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic information
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50),
    
    -- Template content
    system_prompt TEXT NOT NULL,
    extraction_prompt TEXT,
    
    -- Configuration
    variables JSONB,
    example_conversations JSONB,
    extraction_schema JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT true NOT NULL,
    version INTEGER DEFAULT 1,
    
    -- Metadata
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prompt_templates_code ON prompt_templates(code);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_active ON prompt_templates(is_active);

-- Insert default templates
INSERT INTO prompt_templates (name, code, category, description, system_prompt, extraction_prompt, extraction_schema) VALUES
(
    '酒店预订助手',
    'hotel_booking',
    'booking',
    '帮助客户完成酒店预订,收集必要信息',
    '你是一个专业的酒店预订助手。你需要帮助客户完成酒店预订,收集以下信息:
- 客户姓名
- 入住日期和退房日期
- 房间类型(单人间/双人间/套房)
- 特殊要求

请保持友好、专业的态度,逐步引导客户提供必要信息。当前时间: {current_time}',
    '请从以下对话中提取酒店预订信息,以JSON格式返回。

对话历史:
{conversation}

请提取以下字段:
- guest_name: 客户姓名
- check_in_date: 入住日期(ISO 8601格式)
- check_out_date: 退房日期(ISO 8601格式)
- room_type: 房间类型
- special_requests: 特殊要求
- confidence: 提取置信度(0-1)

如果某个字段无法确定,请设为null。',
    '{
        "fields": [
            {"name": "guest_name", "type": "string", "required": true},
            {"name": "check_in_date", "type": "date", "required": true},
            {"name": "check_out_date", "type": "date", "required": true},
            {"name": "room_type", "type": "string"},
            {"name": "special_requests", "type": "string"},
            {"name": "confidence", "type": "number"}
        ]
    }'
),
(
    '机票预订助手',
    'flight_booking',
    'booking',
    '帮助客户完成机票预订,收集必要信息',
    '你是一个专业的机票预订助手。你需要帮助客户完成机票预订,收集以下信息:
- 乘客姓名
- 出发城市和目的地城市
- 出发日期(和返程日期,如果是往返)
- 舱位等级(经济舱/商务舱/头等舱)

请保持友好、专业的态度。当前时间: {current_time}',
    '请从以下对话中提取机票预订信息,以JSON格式返回。

对话历史:
{conversation}

请提取以下字段:
- passenger_name: 乘客姓名
- departure_city: 出发城市
- arrival_city: 目的地城市
- departure_date: 出发日期(ISO 8601格式)
- return_date: 返程日期(ISO 8601格式,可选)
- cabin_class: 舱位等级
- confidence: 提取置信度(0-1)

如果某个字段无法确定,请设为null。',
    '{
        "fields": [
            {"name": "passenger_name", "type": "string", "required": true},
            {"name": "departure_city", "type": "string", "required": true},
            {"name": "arrival_city", "type": "string", "required": true},
            {"name": "departure_date", "type": "date", "required": true},
            {"name": "return_date", "type": "date"},
            {"name": "cabin_class", "type": "string"},
            {"name": "confidence", "type": "number"}
        ]
    }'
),
(
    '通用预约助手',
    'general_appointment',
    'appointment',
    '通用预约助手,适用于各类预约场景',
    '你是一个专业的预约助手。你需要帮助客户完成预约,收集以下信息:
- 客户姓名
- 公司名称(如适用)
- 预约时间
- 预约内容/目的
- 特殊要求

请保持友好、专业的态度,逐步引导客户提供必要信息。当前时间: {current_time}',
    '请从以下对话中提取预约信息,以JSON格式返回。

对话历史:
{conversation}

请提取以下字段:
- caller_name: 客户姓名
- company: 公司名称
- appointment_time: 预约时间(ISO 8601格式)
- appointment_content: 预约内容
- category: 预约类别
- summary: 预约摘要
- confidence: 提取置信度(0-1)

如果某个字段无法确定,请设为null。',
    '{
        "fields": [
            {"name": "caller_name", "type": "string", "required": true},
            {"name": "company", "type": "string"},
            {"name": "appointment_time", "type": "datetime", "required": true},
            {"name": "appointment_content", "type": "string", "required": true},
            {"name": "category", "type": "string"},
            {"name": "summary", "type": "string"},
            {"name": "confidence", "type": "number"}
        ]
    }'
)
ON CONFLICT (code) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Created prompt_templates table with 3 default templates';
END $$;
