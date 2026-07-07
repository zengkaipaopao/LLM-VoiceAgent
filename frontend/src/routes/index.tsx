import { Suspense } from 'react';
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Theme } from '@carbon/react';

import { AppLayout } from '../components/templates/AppLayout/AppLayout';
import { useAuth } from '../auth/AuthContext';
import { lazyWithRetry } from '../utils/lazyWithRetry';

const Login = lazyWithRetry(() =>
  import('../pages/Login').then((module) => ({ default: module.Login }))
);

const Dashboard = lazyWithRetry(() =>
  import('../pages/Dashboard').then((module) => ({ default: module.Dashboard }))
);
const Calls = lazyWithRetry(() =>
  import('../pages/Calls').then((module) => ({ default: module.Calls }))
);
const Prompts = lazyWithRetry(() =>
  import('../pages/Prompts').then((module) => ({ default: module.Prompts }))
);
const Appointments = lazyWithRetry(() =>
  import('../pages/Appointments').then((module) => ({ default: module.Appointments }))
);
const Settings = lazyWithRetry(() =>
  import('../pages/Settings').then((module) => ({ default: module.Settings }))
);
const Pretraining = lazyWithRetry(() =>
  import('../pages/Pretraining').then((module) => ({ default: module.Pretraining }))
);
const Test = lazyWithRetry(() =>
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

const ProtectedLayout = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <Theme theme="g10" className="app-root cds--theme--g10">
        <div style={{ padding: '2rem' }}>正在验证会话…</div>
      </Theme>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <RootLayout />;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <Suspense fallback={<div>正在加载…</div>}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: '/',
    element: <ProtectedLayout />,
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
