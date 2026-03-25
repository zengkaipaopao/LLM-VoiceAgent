import { ReactNode, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  SideNavMenu,
  SideNavMenuItem,
  SkipToContent,
  Theme,
} from '@carbon/react';
import {
  Notification,
  SailboatCoastal,
  UserAvatarFilledAlt,
} from '@carbon/icons-react';
import styles from './AppLayout.module.scss';
import { navLinks, testNavItems } from '../../../config/navigation';
import { LanguageSwitcher } from '../../molecules/LanguageSwitcher';

type AppLayoutProps = {
  children: ReactNode;
};

export function AppLayout({ children }: AppLayoutProps) {
  const { t } = useTranslation(['navigation', 'common']); // 使用多个命名空间
  const location = useLocation();
  const navigate = useNavigate();
  const [isSideNavExpanded, setSideNavExpanded] = useState(false);
  const navRef = useRef<HTMLElement | null>(null);

  const expandNav = () => setSideNavExpanded(true);
  const collapseNav = () => setSideNavExpanded(false);
  const activeTestTab =
    location.pathname === '/test'
      ? new URLSearchParams(location.search).get('tab') ?? testNavItems[0]?.tab ?? 'simulation'
      : null;

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
    // Theme is now managed at App level
    <div className={styles['app-shell']} onMouseMove={handleShellMouseMove}>
      <SkipToContent />
      <Header aria-label="LLM Voice Agent">
        <HeaderMenuButton
          aria-label={isSideNavExpanded ? t('navigation:header.menuCollapse') : t('navigation:header.menuExpand')}
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
          <LanguageSwitcher />
          <HeaderGlobalAction aria-label={t('navigation:header.notifications')}>
            <Notification size={24} />
          </HeaderGlobalAction>
          <HeaderGlobalAction aria-label={t('navigation:header.account')}>
            <UserAvatarFilledAlt size={24} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>
      <SideNav
        ref={navRef}
        expanded={isSideNavExpanded}
        isRail
        addFocusListeners={false}
        aria-label={t('navigation:header.mainNav')}
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
              {t(`navigation:menu.${link.label}`)}
            </SideNavLink>
          ))}
          <SideNavMenu
            title={t('navigation:menu.test')}
            renderIcon={SailboatCoastal}
            isActive={location.pathname === '/test'}
            defaultExpanded={location.pathname === '/test'}
            isSideNavExpanded={isSideNavExpanded}
          >
            {testNavItems.map((item) => {
              const href = `/test?tab=${item.tab}`;
              return (
                <SideNavMenuItem
                  key={item.tab}
                  href={href}
                  isActive={activeTestTab === item.tab}
                  onClick={(event) => {
                    event.preventDefault();
                    goTo(href);
                  }}
                >
                  {t(`navigation:test.${item.label}`)}
                </SideNavMenuItem>
              );
            })}
          </SideNavMenu>
        </SideNavItems>
      </SideNav>
      <Content
        id="main-content"
        className={styles['page-content']}
        onMouseEnter={collapseNav}
      >
        {children}
      </Content>
    </div>
  );
}
