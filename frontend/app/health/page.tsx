'use client';

import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { Heart } from 'lucide-react';

export default function HealthPage() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Header />
      <main className="pl-16 pt-16 min-h-screen">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
              <Heart className="h-6 w-6 text-orange-400" />
            </div>
            <h1 className="text-2xl font-bold">Health</h1>
          </div>
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <p className="text-muted-foreground">Health and habit tracking coming soon.</p>
            <p className="text-sm text-muted-foreground mt-2">Ask Jarvis to help you track habits and wellness!</p>
          </div>
        </div>
      </main>
    </div>
  );
}
