import {
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
} from '@carbon/react';
import { Notification, UserAvatarFilledAlt } from '@carbon/icons-react';

import { LanguageSwitcher } from '../../molecules/LanguageSwitcher';

interface AppHeaderBarProps {
  isSideNavExpanded: boolean;
  onToggleSideNav: () => void;
  onNavigate: (path: string) => void;
  t: (key: string) => string;
}

export function AppHeaderBar({
  isSideNavExpanded,
  onToggleSideNav,
  onNavigate,
  t,
}: AppHeaderBarProps) {
  return (
    <Header aria-label="LLM Voice Agent">
      <HeaderMenuButton
        aria-label={
          isSideNavExpanded ? t('navigation:header.menuCollapse') : t('navigation:header.menuExpand')
        }
        onClick={onToggleSideNav}
        isActive={isSideNavExpanded}
      />

      <HeaderName
        href="/"
        prefix="LLM"
        onClick={(event) => {
          event.preventDefault();
          onNavigate('/');
        }}
      >
        Voice Agent
      </HeaderName>

      <HeaderGlobalBar>
        <LanguageSwitcher />

        <HeaderGlobalAction aria-label={t('navigation:header.notifications')}>
          <Notification size={24} />
        </HeaderGlobalAction>

        <HeaderGlobalAction aria-label={t('navigation:header.account')}>
          <UserAvatarFilledAlt size={24} />
        </HeaderGlobalAction>
      </HeaderGlobalBar>
    </Header>
  );
}
