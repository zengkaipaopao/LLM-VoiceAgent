import 'wicg-inert/dist/inert.esm.js';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import App from './App';
import '@carbon/styles/css/styles.css';
import './styles.css';

const queryClient = new QueryClient();

const router = createBrowserRouter([
  {
    path: '/*',
    element: <App />,
  },
]);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={router}
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>,
);
