import { lazy, Suspense } from 'react';
import { createBrowserRouter, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Theme } from '@carbon/react';

import { AppLayout } from '../components/templates/AppLayout/AppLayout';

const Dashboard = lazy(() =>
  import('../pages/Dashboard').then((module) => ({ default: module.Dashboard }))
);
const Calls = lazy(() =>
  import('../pages/Calls').then((module) => ({ default: module.Calls }))
);
const Prompts = lazy(() =>
  import('../pages/Prompts').then((module) => ({ default: module.Prompts }))
);
const Appointments = lazy(() =>
  import('../pages/Appointments').then((module) => ({ default: module.Appointments }))
);
const Settings = lazy(() =>
  import('../pages/Settings').then((module) => ({ default: module.Settings }))
);
const Pretraining = lazy(() =>
  import('../pages/Pretraining').then((module) => ({ default: module.Pretraining }))
);
const Test = lazy(() =>
  import('../pages/Test').then((module) => ({ default: module.Test }))
);

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
