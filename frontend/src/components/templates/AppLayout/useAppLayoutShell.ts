import { MouseEvent, RefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { normalizeTestTabId, testNavItems } from '../../../config/navigation';

interface UseAppLayoutShellResult {
  pathname: string;
  isSideNavExpanded: boolean;
  navRef: RefObject<HTMLElement | null>;
  activeTestTab: string | null;
  expandNav: () => void;
  collapseNav: () => void;
  toggleSideNav: () => void;
  goTo: (path: string) => void;
  handleShellMouseMove: (event: MouseEvent<HTMLDivElement>) => void;
}

export function useAppLayoutShell(): UseAppLayoutShellResult {
  const location = useLocation();
  const navigate = useNavigate();
  const [isSideNavExpanded, setSideNavExpanded] = useState(false);
  const navRef = useRef<HTMLElement | null>(null);

  const activeTestTab = useMemo(() => {
    if (location.pathname !== '/test') {
      return null;
    }

    const fallback = testNavItems[0]?.tab ?? 'text';
    return normalizeTestTabId(new URLSearchParams(location.search).get('tab') ?? fallback);
  }, [location.pathname, location.search]);

  const expandNav = useCallback(() => {
    setSideNavExpanded(true);
  }, []);

  const collapseNav = useCallback(() => {
    setSideNavExpanded(false);
  }, []);

  const toggleSideNav = useCallback(() => {
    setSideNavExpanded((current) => !current);
  }, []);

  useEffect(() => {
    collapseNav();
  }, [collapseNav, location.pathname]);

  const handleShellMouseMove = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (!isSideNavExpanded || !navRef.current) {
        return;
      }

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
    },
    [collapseNav, isSideNavExpanded]
  );

  const goTo = useCallback(
    (path: string) => {
      navigate(path);
    },
    [navigate]
  );

  return {
    pathname: location.pathname,
    isSideNavExpanded,
    navRef,
    activeTestTab,
    expandNav,
    collapseNav,
    toggleSideNav,
    goTo,
    handleShellMouseMove,
  };
}
