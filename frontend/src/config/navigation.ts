import {
  Calendar,
  Dashboard,
  ModelBuilder,
  Phone,
  SettingsAdjust,
  WatsonHealthTextAnnotationToggle,
  Network_3,
  PhoneVoice,
  WatsonHealthAiStatus,
  User,
} from '@carbon/icons-react';
import type { ComponentType } from 'react';
import { 
  CallSimulationTabContent,
  ReviewerTabContent, 
  AppointmentTabContent, 
  WebSocketTabContent, 
  TwilioTabContent 
} from '../components/organisms/test-tabs';

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

// Test Tab配置类型
export interface TestTabConfig {
  id: string;
  label: string;
  icon: ComponentType;
  component: ComponentType<TabComponentProps>;
}

// 单一数据源：Test Page 的所有 Tab 配置（包含组件）
export const testTabs: TestTabConfig[] = [
  { 
    id: 'call-simulation', 
    label: 'simulation', 
    icon: Phone,
    component: CallSimulationTabContent
  },
  { 
    id: 'appointment', 
    label: 'appointment', 
    icon: User,
    component: AppointmentTabContent
  },
  { 
    id: 'reviewer', 
    label: 'reviewer', 
    icon: WatsonHealthAiStatus,
    component: ReviewerTabContent
  },
  { 
    id: 'websocket', 
    label: 'websocket', 
    icon: Network_3,
    component: WebSocketTabContent
  },
  { 
    id: 'twilio', 
    label: 'twilio', 
    icon: PhoneVoice,
    component: TwilioTabContent
  },
];

// 用于 SideNav 的简化版本（向后兼容）
export const testNavItems = testTabs.map(tab => ({
  tab: tab.id,
  label: tab.label,
}));
