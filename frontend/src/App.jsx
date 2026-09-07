import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import { ToastProvider } from './components/common/Toast';
import InterventionTriage from './pages/InterventionTriage';
import Projects from './pages/Projects';
import ProjectDetails from './pages/ProjectDetails';
import Warnings from './pages/Warnings';
import Escalations from './pages/Escalations';
import AuditTrail from './pages/AuditTrail';
import DemoMode from './pages/DemoMode';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <div className="app-shell min-h-screen text-slate-900 antialiased grid lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="hidden lg:block h-screen sticky top-0 overflow-y-auto overflow-x-hidden">
            <Sidebar />
          </div>
          <div className="min-w-0 flex flex-col min-h-screen">
            <Topbar />
            <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-7 py-5">
              <Routes>
                <Route path="/" element={<InterventionTriage />} />
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
                <Route path="/overview" element={<Navigate to="/" replace />} />
                <Route path="/projects" element={<Projects />} />
                <Route path="/projects/:id" element={<ProjectDetails />} />
                <Route path="/warnings" element={<Warnings />} />
                <Route path="/escalations" element={<Escalations />} />
                <Route path="/audit" element={<AuditTrail />} />
                <Route path="/demo" element={<DemoMode />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <footer className="mx-4 sm:mx-6 lg:mx-7 mb-4 px-5 py-3 rounded-2xl panel text-[10px] text-slate-500 flex items-center justify-between gap-4">
              <div className="flex gap-4">
                <span className="font-semibold text-slate-700">VIGIL Infrastructure Early-Warning System</span>
                <span className="text-slate-400">|</span>
                <span>Deterministic inference with live backend telemetry</span>
              </div>
              <div className="flex gap-4 items-center">
                <span className="font-mono uppercase tracking-widest text-[9px]">TLS 1.3 Strict</span>
                <span className="font-mono uppercase tracking-widest text-[9px] bg-navy-50 text-navy-700 px-2 py-0.5 rounded-full border border-navy-100">Engine v1.0.0</span>
              </div>
            </footer>
          </div>
        </div>
      </ToastProvider>
    </BrowserRouter>
  );
}
