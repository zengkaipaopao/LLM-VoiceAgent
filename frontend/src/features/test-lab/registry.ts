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

const ReviewerTabContent = lazy(() =>
  import('../../components/organisms/TestTabs/ReviewerTabContent').then((module) => ({
    default: module.ReviewerTabContent,
  }))
);

export const testTabComponents: Record<string, ComponentType<TabComponentProps>> = {
  text: TextTestTab,
  voice: VoiceTestTab,
  reviewer: ReviewerTabContent,
};
