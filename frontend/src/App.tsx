import { Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { DashboardPage } from './pages/DashboardPage';
import { CallsPage } from './pages/CallsPage';
import { PromptsPage } from './pages/PromptsPage';
import { AppointmentsPage } from './pages/AppointmentsPage';
import { SettingsPage } from './pages/SettingsPage';
import { PretrainingPage } from './pages/PretrainingPage';
import { TestHub } from './features/test';
import { AppLayout } from './components/AppLayout';

export default function App() {
  return (
    <AppLayout>
      <Suspense fallback={<div>加载中...</div>}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/calls" element={<CallsPage />} />
          <Route path="/appointments" element={<AppointmentsPage />} />
          <Route path="/prompts" element={<PromptsPage />} />
          <Route path="/pretraining" element={<PretrainingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/test" element={<TestHub />} />
        </Routes>
      </Suspense>
    </AppLayout>
  );
}
