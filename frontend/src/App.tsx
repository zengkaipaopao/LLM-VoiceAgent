import { Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { CallsPage } from './pages/CallsPage';
import { PromptsPage } from './pages/PromptsPage';
import { SettingsPage } from './pages/SettingsPage';
import { AnswerTest, DialTest, TestHub } from './features/test';
import { AppStateProvider } from './state/AppStateContext';
import { AppShell } from './components/templates/AppShell';

export default function App() {
  return (
    <AppStateProvider>
      <AppShell>
        <Suspense fallback={<div>加载中...</div>}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/calls" element={<CallsPage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/test" element={<TestHub />} />
            <Route path="/test/dial" element={<DialTest />} />
            <Route path="/test/answer" element={<AnswerTest />} />
          </Routes>
        </Suspense>
      </AppShell>
    </AppStateProvider>
  );
}
