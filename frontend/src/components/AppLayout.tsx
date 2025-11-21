import { ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Content,
  Header,
  HeaderContainer,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
  SideNav,
  SideNavItems,
  SideNavLink,
  SkipToContent,
  Theme,
} from '@carbon/react';
import {
  Dashboard,
  Notification,
  Phone,
  SailboatCoastal,
  SettingsAdjust,
  UserAvatarFilledAlt,
  WatsonHealthTextAnnotationToggle,
} from '@carbon/icons-react';

// Carbon UIShell navigation items; icons help rail mode remain identifiable when collapsed.
const navLinks = [
  { to: '/', label: '仪表盘', icon: Dashboard },
  { to: '/calls', label: '通话记录', icon: Phone },
  { to: '/prompts', label: 'Prompt 管理', icon: WatsonHealthTextAnnotationToggle },
  { to: '/settings', label: '设置', icon: SettingsAdjust },
  { to: '/test', label: '测试', icon: SailboatCoastal },
];

type AppLayoutProps = {
  children: ReactNode;
};

export function AppLayout({ children }: AppLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const goTo = (path: string) => {
    navigate(path);
  };

  return (
    // Use Carbon g10 theme to match UIShell tokens and consistent spacing/colors.
    <Theme theme="g10">
      <HeaderContainer
        render={({ isSideNavExpanded, onClickSideNavExpand }) => (
          <div className="app-shell">
            <SkipToContent />
            <Header aria-label="LLM Voice Agent">
              <HeaderMenuButton
                aria-label={isSideNavExpanded ? '收起菜单' : '展开菜单'}
                onClick={onClickSideNavExpand}
                isActive={isSideNavExpanded}
              />
              <HeaderName
                href="/"
                prefix="LLM"
                onClick={(event) => {
                  event.preventDefault();
                  goTo('/');
                }}
              >
                Voice Agent
              </HeaderName>
              <HeaderGlobalBar>
                <HeaderGlobalAction aria-label="通知">
                  <Notification size={24} />
                </HeaderGlobalAction>
                <HeaderGlobalAction aria-label="账户">
                  <UserAvatarFilledAlt size={24} />
                </HeaderGlobalAction>
              </HeaderGlobalBar>
            </Header>
            <SideNav
              expanded={isSideNavExpanded}
              isRail
              aria-label="主要导航"
              onOverlayClick={onClickSideNavExpand}
            >
              <SideNavItems>
                {navLinks.map((link) => (
                  <SideNavLink
                    key={link.to}
                    href={link.to}
                    isActive={location.pathname === link.to}
                    renderIcon={link.icon}
                    onClick={(event) => {
                      event.preventDefault();
                      goTo(link.to);
                      onClickSideNavExpand();
                    }}
                  >
                    {link.label}
                  </SideNavLink>
                ))}
              </SideNavItems>
            </SideNav>
            <Content id="main-content" className="page-content">
              {children}
            </Content>
          </div>
        )}
      />
    </Theme>
  );
}
