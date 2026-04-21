import { lazy, type ComponentType } from 'react';

import type { TabComponentProps } from '../../config/navigation';

const TextTestTab = lazy(() =>
  import('./text/components/TextTestTab').then((module) => ({
    default: module.TextTestTab,
  }))
);

const VoiceTestTab = lazy(() =>
  import('./voice/components/VoiceTestTab').then((module) => ({
    default: module.VoiceTestTab,
  }))
);

const OfficialBaselineTab = lazy(() =>
  import('./official-demo/components/OfficialBaselineTab').then((module) => ({
    default: module.OfficialBaselineTab,
  }))
);

const ReviewerTabContent = lazy(() =>
  import('../../components/organisms/TestTabs/ReviewerTabContent').then((module) => ({
    default: module.ReviewerTabContent,
  }))
);

export const testTabComponents: Record<string, ComponentType<TabComponentProps>> = {
  text: TextTestTab,
  voice: VoiceTestTab,
  official_demo: OfficialBaselineTab,
  reviewer: ReviewerTabContent,
};
