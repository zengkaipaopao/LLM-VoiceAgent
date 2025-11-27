import { ReactNode } from 'react';
import { AppLayout } from '../AppLayout';

type AppShellProps = {
  children: ReactNode;
};

// Template shell that wraps global navigation and layout chrome.
export function AppShell({ children }: AppShellProps) {
  return <AppLayout>{children}</AppLayout>;
}
