---
description: 创建和应用数据库迁移
---

# 数据库迁移工作流

使用 Alembic 管理数据库 schema 变更,确保开发、测试和生产环境的数据库结构一致。

## 步骤

### 1. 生成迁移文件

当修改了 SQLAlchemy 模型后,生成迁移脚本:

```bash
cd backend
poetry run alembic revision --autogenerate -m "描述性的迁移说明"
```

**示例**:
- `"add user table"`
- `"add index on calls.start_time"`
- `"modify appointment status enum"`

### 2. 审查迁移文件

⚠️ **重要**: 自动生成的迁移可能不完美,必须手动审查!

检查 `backend/alembic/versions/` 中新生成的文件:
- 确认 `upgrade()` 函数正确
- 确认 `downgrade()` 函数可以回滚
- 检查索引、约束是否正确

### 3. 应用迁移

// turbo
```bash
cd backend && poetry run alembic upgrade head
```

### 4. 回滚迁移(如果需要)

```bash
cd backend
# 回滚一个版本
poetry run alembic downgrade -1

# 回滚到特定版本
poetry run alembic downgrade <revision_id>
```

## 最佳实践

- **小步迁移**: 每次迁移只做一件事
- **可逆性**: 确保 downgrade 可以完全回滚
- **测试**: 在开发环境测试 upgrade 和 downgrade
- **数据迁移**: 如果涉及数据转换,添加数据迁移脚本
- **版本控制**: 提交迁移文件到 Git

## 常用命令

```bash
# 查看当前版本
poetry run alembic current

# 查看迁移历史
poetry run alembic history

# 查看 SQL(不执行)
poetry run alembic upgrade head --sql
```
