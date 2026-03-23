'use client';

import { cn } from '@/lib/utils';
import { useDashboardStore } from '@/stores/dashboard';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  Target,
  Zap,
  Wallet,
  Heart,
  Settings,
  ChevronLeft,
  ChevronRight,
  Command,
  Bot,
  Cpu,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NavItem {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
  color?: string;
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/', color: 'text-white' },
  { icon: Bot, label: 'Jarvis', href: '/jarvis', color: 'text-cyan-400' },
  { icon: Cpu, label: 'Ultron', href: '/ultron', color: 'text-red-500' },
  { icon: Target, label: 'Goals', href: '/goals', color: 'text-purple-400' },
  { icon: Zap, label: 'Skills', href: '/skills', color: 'text-blue-400' },
  { icon: Wallet, label: 'Money', href: '/money', color: 'text-emerald-400' },
  { icon: Heart, label: 'Health', href: '/health', color: 'text-orange-400' },
];

export function Sidebar() {
  const { sidebarOpen, toggleSidebar, toggleChatPanel, chatPanelOpen } = useDashboardStore();
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen transition-all duration-300 ease-in-out',
        'flex flex-col border-r border-border bg-background',
        sidebarOpen ? 'w-56' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
            <Command className="h-5 w-5 text-emerald-400" />
          </div>
          {sidebarOpen && (
            <span className="text-lg font-bold tracking-tight">
              <span className="text-gradient-green">NEXUS</span>
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={toggleSidebar}
        >
          {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              title={!sidebarOpen ? item.label : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-200',
                'hover:bg-white/5',
                isActive && 'bg-white/5 border border-white/10',
                !sidebarOpen && 'justify-center'
              )}
            >
              <Icon className={cn('h-5 w-5 flex-shrink-0', isActive ? item.color : 'text-muted-foreground')} />
              {sidebarOpen && (
                <span className={cn('text-sm font-medium', isActive ? 'text-white' : 'text-muted-foreground')}>
                  {item.label}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* AI Chat Toggle */}
      <div className="border-t border-border p-3">
        <Button
          variant="ghost"
          title={!sidebarOpen ? 'Nexus AI' : undefined}
          className={cn(
            'w-full justify-start gap-3 px-3',
            !sidebarOpen && 'justify-center',
            chatPanelOpen && 'bg-emerald-500/10 text-emerald-400'
          )}
          onClick={toggleChatPanel}
        >
          <div className="relative">
            <div className="flex h-5 w-5 items-center justify-center">
              <span className="text-sm font-mono font-bold">AI</span>
            </div>
            <div className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          {sidebarOpen && <span className="text-sm font-medium">Nexus AI</span>}
        </Button>
      </div>

      {/* Settings */}
      <div className="border-t border-border p-3">
        <Link
          href="/settings"
          title={!sidebarOpen ? 'Settings' : undefined}
          className={cn(
            'flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-200',
            'hover:bg-white/5',
            pathname === '/settings' ? 'bg-white/5 border border-white/10 text-white' : 'text-muted-foreground hover:text-foreground',
            !sidebarOpen && 'justify-center'
          )}
        >
          <Settings className="h-5 w-5 flex-shrink-0" />
          {sidebarOpen && <span className="text-sm font-medium">Settings</span>}
        </Link>
      </div>
    </aside>
  );
}
