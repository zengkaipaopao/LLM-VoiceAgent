import {
  Calendar,
  Dashboard,
  ModelBuilder,
  Chat,
  Phone,
  SettingsAdjust,
  WatsonHealthTextAnnotationToggle,
  PhoneVoice,
  WatsonHealthAiStatus,
} from '@carbon/icons-react';
import { normalizeTestTabId } from '../features/test-lab/shared/navigation/tabIds';

export const navLinks = [
  { to: '/', label: 'dashboard', icon: Dashboard },
  { to: '/calls', label: 'calls', icon: Phone },
  { to: '/appointments', label: 'appointments', icon: Calendar },
  { to: '/prompts', label: 'prompts', icon: WatsonHealthTextAnnotationToggle },
  { to: '/pretraining', label: 'pretraining', icon: ModelBuilder },
  { to: '/settings', label: 'settings', icon: SettingsAdjust },
];

// Tab组件的Props接口
export interface TabComponentProps {
  enableReviewer?: boolean;
  onToggle?: (enabled: boolean) => void;
}

export interface TestTabNavItem {
  id: string;
  label: string;
  icon: typeof Chat;
}

export { normalizeTestTabId };

// 单一数据源：Test Page 的所有 Tab 导航元数据
export const testTabs: TestTabNavItem[] = [
  {
    id: 'text',
    label: 'text',
    icon: Chat,
  },
  {
    id: 'voice',
    label: 'voice',
    icon: PhoneVoice,
  },
  {
    id: 'reviewer',
    label: 'reviewer',
    icon: WatsonHealthAiStatus,
  },
];

// 用于 SideNav 的简化版本（向后兼容）
export const testNavItems = testTabs.map((tab) => ({
  tab: tab.id,
  label: tab.label,
}));
