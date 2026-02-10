import { createBrowserRouter, Outlet } from 'react-router-dom';
import { DashboardPage } from '../pages/DashboardPage';
import { CallsPage } from '../pages/CallsPage';
import { PromptsPage } from '../pages/PromptsPage';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { SettingsPage } from '../pages/SettingsPage';
import { PretrainingPage } from '../pages/PretrainingPage';
import { TestPage } from '../pages/TestPage';
import { AppLayout } from '../components/templates/AppLayout/AppLayout';
import { Theme } from '@carbon/react';
import { Suspense } from 'react';

// Root layout wrapper
const RootLayout = () => (
  <Theme theme="g10" className="app-root cds--theme--g10">
    <AppLayout>
      <Suspense fallback={<div>加载中...</div>}>
        <Outlet />
      </Suspense>
    </AppLayout>
  </Theme>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'calls',
        element: <CallsPage />,
      },
      {
        path: 'appointments',
        element: <AppointmentsPage />,
      },
      {
        path: 'prompts',
        element: <PromptsPage />,
      },
      {
        path: 'pretraining',
        element: <PretrainingPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: 'test',
        element: <TestPage />,
      },
    ],
  },
], {
  future: {
    v7_relativeSplatPath: true,
  },
});
