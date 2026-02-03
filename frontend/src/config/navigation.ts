import {
  Calendar,
  Dashboard,
  ModelBuilder,
  Phone,
  SettingsAdjust,
  WatsonHealthTextAnnotationToggle,
} from '@carbon/icons-react';

export const navLinks = [
  { to: '/', label: 'dashboard', icon: Dashboard },
  { to: '/calls', label: 'calls', icon: Phone },
  { to: '/appointments', label: 'appointments', icon: Calendar },
  { to: '/prompts', label: 'prompts', icon: WatsonHealthTextAnnotationToggle },
  { to: '/pretraining', label: 'pretraining', icon: ModelBuilder },
  { to: '/settings', label: 'settings', icon: SettingsAdjust },
];

export const testNavItems = [
  { tab: 'websocket', label: 'WebSocket' },
  { tab: 'twilio', label: 'Twilio WebCall' },
];
