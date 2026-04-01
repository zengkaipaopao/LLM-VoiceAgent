import { RefObject } from 'react';
import {
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
} from '@carbon/react';
import { SailboatCoastal } from '@carbon/icons-react';

import { navLinks, testNavItems } from '../../../config/navigation';

interface AppSideNavigationProps {
  isSideNavExpanded: boolean;
  pathname: string;
  activeTestTab: string | null;
  navRef: RefObject<HTMLElement | null>;
  onNavigate: (path: string) => void;
  onExpandNav: () => void;
  t: (key: string) => string;
}

export function AppSideNavigation({
  isSideNavExpanded,
  pathname,
  activeTestTab,
  navRef,
  onNavigate,
  onExpandNav,
  t,
}: AppSideNavigationProps) {
  return (
    <SideNav
      ref={navRef}
      expanded={isSideNavExpanded}
      isRail
      addFocusListeners={false}
      aria-label={t('navigation:header.mainNav')}
      onMouseEnter={onExpandNav}
    >
      <SideNavItems>
        {navLinks.map((link) => (
          <SideNavLink
            key={link.to}
            href={link.to}
            isActive={pathname === link.to}
            renderIcon={link.icon}
            onClick={(event) => {
              event.preventDefault();
              onNavigate(link.to);
            }}
          >
            {t(`navigation:menu.${link.label}`)}
          </SideNavLink>
        ))}

        <SideNavMenu
          title={t('navigation:menu.test')}
          renderIcon={SailboatCoastal}
          isActive={pathname === '/test'}
          defaultExpanded={pathname === '/test'}
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
                  onNavigate(href);
                }}
              >
                {t(`navigation:test.${item.label}`)}
              </SideNavMenuItem>
            );
          })}
        </SideNavMenu>
      </SideNavItems>
    </SideNav>
  );
}
