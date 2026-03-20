'use client';

import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { WidgetGrid } from '@/components/layout/WidgetGrid';
import { AIChatPanel } from '@/components/chat/AIChatPanel';
import { JarvisVoiceUI } from '@/components/jarvis';
import { TarsVoiceUI } from '@/components/tars';

export default function DashboardPage() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Header />
      <WidgetGrid />
      <AIChatPanel />
      {/* AI Assistants - TARS on left, Jarvis on right */}
      <TarsVoiceUI />
      <JarvisVoiceUI />
    </div>
  );
}
