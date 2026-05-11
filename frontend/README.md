# LLMVoiceDesk - 前端

企业级语音 AI 助手前端应用

## 🚀 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

---

## 📁 项目结构

```
frontend/
├── src/
│   ├── components/      # UI组件(原子化设计)
│   ├── pages/          # 页面组件
│   ├── features/       # 功能模块
│   ├── api/            # API客户端
│   └── config/         # 配置文件
├── docs/               # 开发文档
└── public/             # 静态资源
```

---

## 📚 文档

- [开发指南](./docs/DEVELOPMENT_GUIDE.md)
- [原子化设计](./docs/ATOMIC_DESIGN.md)
- [项目结构](./docs/PROJECT_STRUCTURE.md)

---

## 🛠️ 技术栈

- **框架**: React 18.2+
- **语言**: TypeScript 5.0+
- **构建工具**: Vite 5.0+
- **UI库**: IBM Carbon Design System 1.50+
- **数据管理**: React Query 5.0+
- **国际化**: i18next 23.0+

---

## 🎨 设计系统

项目采用 [IBM Carbon Design System](https://carbondesignsystem.com/)，遵循企业级UI设计规范。

### 主题配置
- 默认主题: `g10` (白色背景)
- 支持深色模式: `g100`

---

## 🌍 国际化

支持以下语言：
- 🇨🇳 简体中文
- 🇺🇸 English
- 🇯🇵 日本語

---

## 📦 构建部署

### 开发构建
```bash
npm run dev
```

### 生产构建
```bash
npm run build
```

### 预览生产构建
```bash
npm run preview
```

---

## 🧪 测试

```bash
# 运行测试
npm run test

# 测试覆盖率
npm run test:coverage
```

---

## 📝 开发规范

请参考 [开发指南](./docs/DEVELOPMENT_GUIDE.md) 了解：
- 代码规范
- 组件开发
- 状态管理
- 性能优化

---

## 📞 相关链接

- [后端文档](../backend/README.md)
- [项目架构](../docs/ARCHITECTURE.md)
- [Carbon Design System](https://carbondesignsystem.com/)
