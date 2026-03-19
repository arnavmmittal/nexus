'use client';

import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { WidgetGrid } from '@/components/layout/WidgetGrid';
import { AIChatPanel } from '@/components/chat/AIChatPanel';

export default function DashboardPage() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Header />
      <WidgetGrid />
      <AIChatPanel />
    </div>
  );
}
