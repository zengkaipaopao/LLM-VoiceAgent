import { jsx as _jsx } from "react/jsx-runtime";
import { PageTemplate } from '../../components/templates/PageTemplate';
import { EmptyState } from '../../components/organisms/EmptyState';
/**
 * TestHub - 实时调试实验室页面
 *
 * 用于测试WebSocket和Twilio WebCall等链路
 * 当前为空状态骨架,等待后续业务逻辑实现
 */
export function TestHub() {
    return (_jsx(PageTemplate, { title: "\u5B9E\u65F6\u8C03\u8BD5\u5B9E\u9A8C\u5BA4", subtitle: "\u5728\u5355\u4E00\u754C\u9762\u4F53\u9A8C WebSocket \u4EE5\u53CA Twilio WebCall \u7B49\u94FE\u8DEF,\u65B9\u4FBF\u6BD4\u5BF9\u3002", children: _jsx(EmptyState, { title: "\u6D4B\u8BD5\u529F\u80FD\u5F00\u53D1\u4E2D", description: "\u6B64\u9875\u9762\u5C06\u63D0\u4F9BWebSocket\u548CTwilio WebCall\u7684\u5B9E\u65F6\u8C03\u8BD5\u529F\u80FD\u3002" }) }));
}
