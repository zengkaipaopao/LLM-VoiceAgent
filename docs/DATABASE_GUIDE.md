# 数据库设计指南

**版本**: 1.0

---

## 数据库选型

**推荐**: PostgreSQL 16+

**原因**:
- ✅ 强大的JSONB支持
- ✅ 完整的事务支持
- ✅ 丰富的索引类型
- ✅ 成熟的生态系统

---

## 核心表设计

### calls表 (通话记录)

```sql
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_number VARCHAR(20) NOT NULL,
    callee_number VARCHAR(20) NOT NULL,
    session_id VARCHAR(100) UNIQUE,
    status VARCHAR(20) NOT NULL,
    transcript TEXT,
    recording_url VARCHAR(500),
    duration_seconds FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_calls_caller ON calls(caller_number);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_created ON calls(created_at DESC);
```

### appointments表 (预约记录)

```sql
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID REFERENCES calls(id),
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    appointment_time TIMESTAMP NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_appt_time ON appointments(appointment_time);
CREATE INDEX idx_appt_status ON appointments(status);
```

### extracted_info表 (提取信息)

```sql
CREATE TABLE extracted_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_extracted_call ON extracted_info(call_id);
```

---

## SQLAlchemy模型

### 基础模型

```python
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from uuid import uuid4

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Call模型

```python
from sqlalchemy import Column, String, Text, Float, Enum
from sqlalchemy.dialects.postgresql import JSONB

class Call(BaseModel):
    __tablename__ = "calls"
    
    caller_number = Column(String(20), nullable=False, index=True)
    callee_number = Column(String(20), nullable=False)
    session_id = Column(String(100), unique=True)
    status = Column(String(20), nullable=False, index=True)
    transcript = Column(Text)
    recording_url = Column(String(500))
    duration_seconds = Column(Float)
    metadata = Column(JSONB, default=dict)
```

---

## 数据库迁移

### 使用Alembic

```bash
# 初始化
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "Add calls table"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 迁移文件示例

```python
def upgrade():
    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(), primary_key=True),
        sa.Column('caller_number', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    op.create_index('ix_calls_caller', 'calls', ['caller_number'])

def downgrade():
    op.drop_table('calls')
```

---

## 查询优化

### 1. 使用索引

```python
# 为常用查询字段添加索引
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_created ON calls(created_at DESC);
```

### 2. 避免N+1查询

```python
# ❌ 错误
calls = session.query(Call).all()
for call in calls:
    prompt = session.query(Prompt).get(call.prompt_id)

# ✅ 正确
from sqlalchemy.orm import joinedload
calls = session.query(Call).options(joinedload(Call.prompt)).all()
```

### 3. 分页查询

```python
def list_calls(skip: int = 0, limit: int = 100):
    return session.query(Call)\
        .offset(skip)\
        .limit(limit)\
        .all()
```

---

## 备份策略

### 自动备份

```bash
# 每日备份
0 2 * * * pg_dump llm_voice > /backup/db_$(date +\%Y\%m\%d).sql

# 保留30天
find /backup -name "db_*.sql" -mtime +30 -delete
```

### 恢复

```bash
psql llm_voice < /backup/db_20260203.sql
```

---

## 最佳实践

1. ✅ 使用UUID作为主键
2. ✅ 添加created_at和updated_at
3. ✅ 为查询字段添加索引
4. ✅ 使用外键约束
5. ✅ JSONB存储非结构化数据
6. ✅ 定期备份
7. ✅ 使用连接池
8. ✅ 监控慢查询
