'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Bot, Cpu, ChevronDown } from 'lucide-react';

interface Agent {
  id: 'jarvis' | 'ultron';
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
  href: string;
}

const agents: Agent[] = [
  {
    id: 'jarvis',
    name: 'Jarvis',
    icon: Bot,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/30',
    description: 'Helpful AI Assistant',
    href: '/jarvis',
  },
  {
    id: 'ultron',
    name: 'Ultron',
    icon: Cpu,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    description: 'Autonomous Operations',
    href: '/ultron',
  },
];

interface AgentSwitcherProps {
  variant?: 'dropdown' | 'tabs' | 'floating';
  className?: string;
}

export function AgentSwitcher({ variant = 'tabs', className }: AgentSwitcherProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  const currentAgent = agents.find(a => pathname.startsWith(a.href)) || agents[0];

  const handleAgentChange = (agent: Agent) => {
    router.push(agent.href);
    setIsOpen(false);
  };

  if (variant === 'dropdown') {
    return (
      <div className={cn('relative', className)}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            'flex items-center gap-3 px-4 py-2.5 rounded-xl',
            'bg-white/5 border border-white/10 backdrop-blur-xl',
            'hover:bg-white/10 transition-colors'
          )}
        >
          <div className={cn('p-1.5 rounded-lg', currentAgent.bgColor, currentAgent.borderColor, 'border')}>
            <currentAgent.icon className={cn('w-4 h-4', currentAgent.color)} />
          </div>
          <div className="text-left">
            <div className="text-sm font-medium">{currentAgent.name}</div>
            <div className="text-[10px] text-white/50">{currentAgent.description}</div>
          </div>
          <ChevronDown className={cn(
            'w-4 h-4 text-white/50 transition-transform',
            isOpen && 'rotate-180'
          )} />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute top-full left-0 mt-2 w-full rounded-xl bg-black/90 border border-white/10 backdrop-blur-xl z-50 overflow-hidden">
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => handleAgentChange(agent)}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-3',
                    'hover:bg-white/5 transition-colors',
                    currentAgent.id === agent.id && 'bg-white/5'
                  )}
                >
                  <div className={cn('p-1.5 rounded-lg', agent.bgColor, agent.borderColor, 'border')}>
                    <agent.icon className={cn('w-4 h-4', agent.color)} />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-medium">{agent.name}</div>
                    <div className="text-[10px] text-white/50">{agent.description}</div>
                  </div>
                  {currentAgent.id === agent.id && (
                    <div className={cn('ml-auto w-2 h-2 rounded-full', agent.color.replace('text-', 'bg-'))} />
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    );
  }

  if (variant === 'tabs') {
    return (
      <div className={cn('flex gap-2', className)}>
        {agents.map((agent) => {
          const isActive = pathname.startsWith(agent.href);
          return (
            <button
              key={agent.id}
              onClick={() => handleAgentChange(agent)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-xl transition-all',
                'border backdrop-blur-xl',
                isActive
                  ? cn(agent.bgColor, agent.borderColor, agent.color)
                  : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10'
              )}
            >
              <agent.icon className="w-4 h-4" />
              <span className="text-sm font-medium">{agent.name}</span>
              {isActive && (
                <div className={cn(
                  'w-1.5 h-1.5 rounded-full animate-pulse',
                  agent.id === 'jarvis' ? 'bg-cyan-400' : 'bg-red-400'
                )} />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  // Floating variant
  return (
    <div className={cn(
      'fixed bottom-6 left-1/2 -translate-x-1/2 z-50',
      'flex gap-2 p-2 rounded-2xl',
      'bg-black/80 border border-white/10 backdrop-blur-xl',
      className
    )}>
      {agents.map((agent) => {
        const isActive = pathname.startsWith(agent.href);
        return (
          <button
            key={agent.id}
            onClick={() => handleAgentChange(agent)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl transition-all',
              isActive
                ? cn(agent.bgColor, 'border', agent.borderColor)
                : 'hover:bg-white/5'
            )}
          >
            <div className="relative">
              <agent.icon className={cn('w-5 h-5', isActive ? agent.color : 'text-white/60')} />
              {isActive && (
                <div className={cn(
                  'absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full',
                  agent.id === 'jarvis' ? 'bg-cyan-400' : 'bg-red-400',
                  'animate-pulse'
                )} />
              )}
            </div>
            <span className={cn(
              'text-sm font-medium',
              isActive ? agent.color : 'text-white/60'
            )}>
              {agent.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
