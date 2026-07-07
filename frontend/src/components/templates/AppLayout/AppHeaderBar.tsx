import {
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
} from '@carbon/react';
import { Logout, Notification } from '@carbon/icons-react';

import { useAuth } from '../../../auth/AuthContext';
import { LanguageSwitcher } from '../../molecules/LanguageSwitcher';
import styles from './AppLayout.module.scss';

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
  const { user, logout } = useAuth();

  return (
    <Header aria-label="LLM VoiceDesk">
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
        className={styles['brand-name']}
        onClick={(event) => {
          event.preventDefault();
          onNavigate('/');
        }}
      >
        <span className={styles['brand-lockup']}>
          <span className={styles['brand-mark']} aria-hidden="true">
            VD
          </span>
          <span>VoiceDesk</span>
        </span>
      </HeaderName>

      <HeaderGlobalBar>
        <LanguageSwitcher />

        <HeaderGlobalAction aria-label={t('navigation:header.notifications')}>
          <Notification size={24} />
        </HeaderGlobalAction>

        <HeaderGlobalAction
          aria-label={`退出登录（${user?.display_name || user?.username || ''}）`}
          onClick={() => void logout()}
        >
          <Logout size={24} />
        </HeaderGlobalAction>
      </HeaderGlobalBar>
    </Header>
  );
}
