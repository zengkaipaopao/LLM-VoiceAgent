import { ReactNode, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Content,
  Header,
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
  const [isSideNavExpanded, setSideNavExpanded] = useState(false);
  const navRef = useRef<HTMLElement | null>(null);

  const expandNav = () => setSideNavExpanded(true);
  const collapseNav = () => setSideNavExpanded(false);

  // 路由切换后默认收起，防止状态滞留
  useEffect(() => {
    collapseNav();
  }, [location.pathname]);

  // 若展开状态且指针离开侧栏矩形，则收起
  const handleShellMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!isSideNavExpanded || !navRef.current) return;
    const rect = navRef.current.getBoundingClientRect();
    const { clientX, clientY } = event;
    const outsideNav =
      clientX < rect.left ||
      clientX > rect.right ||
      clientY < rect.top ||
      clientY > rect.bottom;

    if (outsideNav) {
      collapseNav();
    }
  };

  const goTo = (path: string) => {
    navigate(path);
  };

  return (
    // Use Carbon g10 theme to match UIShell tokens and consistent spacing/colors.
    <Theme theme="g10">
      <div className="app-shell" onMouseMove={handleShellMouseMove}>
        <SkipToContent />
        <Header aria-label="LLM Voice Agent">
          <HeaderMenuButton
            aria-label={isSideNavExpanded ? '收起菜单' : '展开菜单'}
            onClick={() => setSideNavExpanded((prev) => !prev)}
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
          ref={navRef}
          expanded={isSideNavExpanded}
          isRail
          addFocusListeners={false}
          aria-label="主要导航"
          onMouseEnter={expandNav}
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
                  // 点击仅导航，不折叠；移出侧边栏区域再收起。
                }}
              >
                {link.label}
              </SideNavLink>
            ))}
          </SideNavItems>
        </SideNav>
        <Content
          id="main-content"
          className="page-content"
          onMouseEnter={collapseNav}
        >
          {children}
        </Content>
      </div>
    </Theme>
  );
}
