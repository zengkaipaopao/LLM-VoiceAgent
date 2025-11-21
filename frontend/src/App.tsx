import { Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { CallsPage } from './pages/CallsPage';
import { PromptsPage } from './pages/PromptsPage';
import { SettingsPage } from './pages/SettingsPage';
import { TestPage } from './pages/TestPage';
import { AppStateProvider } from './state/AppStateContext';

export default function App() {
  return (
    <AppStateProvider>
      <AppLayout>
        <Suspense fallback={<div>加载中...</div>}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/calls" element={<CallsPage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/test" element={<TestPage />} />
          </Routes>
        </Suspense>
      </AppLayout>
    </AppStateProvider>
  );
}
