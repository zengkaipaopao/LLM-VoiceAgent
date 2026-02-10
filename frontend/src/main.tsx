import './config/i18n'; // 初始化i18n
import 'wicg-inert/dist/inert.esm.js';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { ErrorBoundary } from './components/utils/ErrorBoundary';
import { router } from './routes';
import './styles/theme.scss';
import './styles/global.scss';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={router}
        future={{
          v7_startTransition: true,
        }}
      />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
