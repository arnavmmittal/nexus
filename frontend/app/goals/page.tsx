'use client';

import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { Target } from 'lucide-react';

export default function GoalsPage() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Header />
      <main className="pl-16 pt-16 min-h-screen">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
              <Target className="h-6 w-6 text-purple-400" />
            </div>
            <h1 className="text-2xl font-bold">Goals</h1>
          </div>
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <p className="text-muted-foreground">Goal tracking coming soon.</p>
            <p className="text-sm text-muted-foreground mt-2">Ask Jarvis to help you set and track goals!</p>
          </div>
        </div>
      </main>
    </div>
  );
}
