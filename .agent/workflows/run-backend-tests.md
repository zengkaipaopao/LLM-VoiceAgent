---
description: 运行后端单元测试和集成测试
---

# 运行后端测试

执行后端的完整测试套件,包括单元测试和集成测试,并生成覆盖率报告。

## 步骤

// turbo
1. 切换到后端目录并运行测试
```bash
cd backend && poetry run pytest -v --cov=app --cov-report=term-missing --cov-report=html
```

2. 查看覆盖率报告
   - 终端会显示覆盖率摘要
   - HTML 报告生成在 `backend/htmlcov/index.html`

## 可选参数

- 只运行单元测试: `poetry run pytest -m "not integration"`
- 只运行集成测试: `poetry run pytest -m integration`
- 并行运行: `poetry run pytest -n auto` (需要安装 pytest-xdist)
- 运行特定文件: `poetry run pytest tests/test_specific.py`

## 覆盖率要求

- 新功能代码覆盖率应 ≥ 80%
- 关键路径(通话流程、信息提取)必须有集成测试
