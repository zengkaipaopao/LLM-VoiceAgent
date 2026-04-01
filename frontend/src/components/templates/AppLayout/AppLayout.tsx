import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Content, SkipToContent } from '@carbon/react';

import { AppHeaderBar } from './AppHeaderBar';
import { AppSideNavigation } from './AppSideNavigation';
import { useAppLayoutShell } from './useAppLayoutShell';
import styles from './AppLayout.module.scss';

type AppLayoutProps = {
  children: ReactNode;
};

export function AppLayout({ children }: AppLayoutProps) {
  const { t } = useTranslation(['navigation', 'common']);
  const {
    pathname,
    isSideNavExpanded,
    navRef,
    activeTestTab,
    expandNav,
    collapseNav,
    toggleSideNav,
    goTo,
    handleShellMouseMove,
  } = useAppLayoutShell();

  return (
    <div className={styles['app-shell']} onMouseMove={handleShellMouseMove}>
      <SkipToContent />

      <AppHeaderBar
        isSideNavExpanded={isSideNavExpanded}
        onToggleSideNav={toggleSideNav}
        onNavigate={goTo}
        t={t}
      />

      <AppSideNavigation
        isSideNavExpanded={isSideNavExpanded}
        pathname={pathname}
        activeTestTab={activeTestTab}
        navRef={navRef}
        onNavigate={goTo}
        onExpandNav={expandNav}
        t={t}
      />

      <Content id="main-content" className={styles['page-content']} onMouseEnter={collapseNav}>
        {children}
      </Content>
    </div>
  );
}
