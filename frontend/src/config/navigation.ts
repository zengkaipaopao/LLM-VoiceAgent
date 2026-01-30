import {
  Calendar,
  Dashboard,
  ModelBuilder,
  Phone,
  SettingsAdjust,
  WatsonHealthTextAnnotationToggle,
} from '@carbon/icons-react';

export const navLinks = [
  { to: '/', label: '仪表盘', icon: Dashboard },
  { to: '/calls', label: '通话记录', icon: Phone },
  { to: '/appointments', label: '预约记录', icon: Calendar },
  { to: '/prompts', label: 'Prompt 管理', icon: WatsonHealthTextAnnotationToggle },
  { to: '/pretraining', label: '微调', icon: ModelBuilder },
  { to: '/settings', label: '设置', icon: SettingsAdjust },
];

export const testNavItems = [
  { tab: 'websocket', label: 'WebSocket' },
  { tab: 'twilio', label: 'Twilio WebCall' },
];
