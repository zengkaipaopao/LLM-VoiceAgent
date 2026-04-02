import { createBrowserRouter, Outlet } from 'react-router-dom';
import { Dashboard } from '../pages/Dashboard';
import { Calls } from '../pages/Calls';
import { Prompts } from '../pages/Prompts';
import { Appointments } from '../pages/Appointments';
import { Settings } from '../pages/Settings';
import { Pretraining } from '../pages/Pretraining';
import { Test } from '../pages/Test';
import { AppLayout } from '../components/templates/AppLayout/AppLayout';
import { Theme } from '@carbon/react';
import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';

// Root layout wrapper
const RootLayout = () => {
  const { t } = useTranslation(['common']);

  return (
    <Theme theme="g10" className="app-root cds--theme--g10">
      <AppLayout>
        <Suspense fallback={<div>{t('common:status.loading')}</div>}>
          <Outlet />
        </Suspense>
      </AppLayout>
    </Theme>
  );
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: 'calls',
        element: <Calls />,
      },
      {
        path: 'appointments',
        element: <Appointments />,
      },
      {
        path: 'prompts',
        element: <Prompts />,
      },
      {
        path: 'pretraining',
        element: <Pretraining />,
      },
      {
        path: 'settings',
        element: <Settings />,
      },
      {
        path: 'test',
        element: <Test />,
      },
    ],
  },
], {
  future: {
    v7_relativeSplatPath: true,
  },
});
