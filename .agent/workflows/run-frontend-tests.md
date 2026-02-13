---
description: 运行前端测试套件
---

# 运行前端测试

执行前端的测试套件,包括组件测试和集成测试,并生成覆盖率报告。

## 步骤

// turbo
1. 切换到前端目录并运行测试
```bash
cd frontend && npm run test:coverage
```

2. 查看测试结果
   - 终端显示测试结果和覆盖率
   - 覆盖率报告生成在 `frontend/coverage/`

## 可选命令

- 监听模式(开发时使用): `npm run test:watch`
- UI 模式(可视化界面): `npm run test:ui`
- 运行特定测试: `npm run test -- CallCard.test.tsx`

## 测试最佳实践

- 使用 React Testing Library 测试用户交互
- Mock API 调用和外部依赖
- 遵循 AAA 模式(Arrange-Act-Assert)
