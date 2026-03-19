'use client';

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useDashboardStore } from '@/stores/dashboard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Maximize2,
  Minimize2,
  RotateCcw,
  Mic,
  Command,
} from 'lucide-react';

export function AIChatPanel() {
  const {
    chatPanelOpen,
    setChatPanelOpen,
    chatMessages,
    addChatMessage,
    chatInput,
    setChatInput,
    isChatLoading,
    setChatLoading,
    clearChat,
  } = useDashboardStore();

  const [isExpanded, setIsExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Focus input when panel opens
  useEffect(() => {
    if (chatPanelOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [chatPanelOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput('');

    // Add user message
    addChatMessage({ role: 'user', content: userMessage });

    // Simulate AI response
    setChatLoading(true);
    setTimeout(() => {
      const responses = [
        `Based on your current goals and patterns, I'd suggest focusing on your Python practice today. You're on a 23-day streak - let's keep it going!`,
        `Looking at your schedule, you have a clear 2-hour block this afternoon. That's perfect for deep work on the Nexus project.`,
        `Your sleep was 7.2 hours last night - that's above your average. You should have good energy for challenging tasks today.`,
        `I noticed your bench press is at 185 lbs, 82% to your goal. Based on your progress rate, you'll hit 225 lbs by mid-April.`,
      ];
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      addChatMessage({ role: 'assistant', content: randomResponse });
      setChatLoading(false);
    }, 1000);
  };

  const handleQuickCommand = (command: string) => {
    setChatInput(command);
    inputRef.current?.focus();
  };

  const quickCommands = [
    { label: '/focus', description: 'Set focus task' },
    { label: '/log', description: 'Log activity' },
    { label: '/status', description: 'Quick status' },
  ];

  if (!chatPanelOpen) return null;

  return (
    <aside
      className={cn(
        'fixed right-0 top-0 z-40 h-screen border-l border-border bg-background/95 backdrop-blur-xl',
        'flex flex-col transition-all duration-300',
        isExpanded ? 'w-[600px]' : 'w-96'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-blue-500/20 border border-emerald-500/30">
              <Command className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full bg-emerald-500 border-2 border-background animate-pulse" />
          </div>
          <div>
            <h2 className="font-semibold text-sm">Nexus AI</h2>
            <p className="text-xs text-muted-foreground">Your personal assistant</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={clearChat}
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={() => setChatPanelOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4">
          {/* Welcome message if no messages */}
          {chatMessages.length === 0 && (
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                  <Sparkles className="h-4 w-4 text-emerald-400" />
                </div>
                <div className="flex-1 glass-panel rounded-xl p-4">
                  <p className="text-sm leading-relaxed">
                    Good afternoon, Arnav! I&apos;m Nexus, your personal AI assistant. I have access to all your goals, skills, and patterns.
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    You have <span className="text-emerald-400 font-medium">3 priorities</span> today. Your energy is high - perfect for tackling the Nexus design docs first.
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    How can I help you today?
                  </p>
                </div>
              </div>

              {/* Quick Commands */}
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">Quick commands:</p>
                <div className="flex flex-wrap gap-2">
                  {quickCommands.map((cmd) => (
                    <Button
                      key={cmd.label}
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs border-border hover:border-emerald-500/50 hover:bg-emerald-500/5"
                      onClick={() => handleQuickCommand(cmd.label)}
                    >
                      <span className="text-emerald-400 font-mono">{cmd.label}</span>
                      <span className="text-muted-foreground ml-1.5">{cmd.description}</span>
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          {chatMessages.map((message) => (
            <div
              key={message.id}
              className={cn('flex items-start gap-3', message.role === 'user' && 'flex-row-reverse')}
            >
              <div
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0',
                  message.role === 'assistant' ? 'bg-emerald-500/10' : 'bg-blue-500/10'
                )}
              >
                {message.role === 'assistant' ? (
                  <Bot className="h-4 w-4 text-emerald-400" />
                ) : (
                  <User className="h-4 w-4 text-blue-400" />
                )}
              </div>
              <div
                className={cn(
                  'flex-1 rounded-xl p-3 max-w-[85%]',
                  message.role === 'assistant'
                    ? 'glass-panel'
                    : 'bg-blue-500/10 border border-blue-500/20'
                )}
              >
                <p className="text-sm leading-relaxed">{message.content}</p>
                <p className="text-xs text-muted-foreground mt-1.5">
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isChatLoading && (
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                <Bot className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="glass-panel rounded-xl p-3">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:-0.3s]" />
                    <div className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:-0.15s]" />
                    <div className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce" />
                  </div>
                  <span className="text-xs text-muted-foreground">Thinking...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t border-border p-4">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <div className="relative flex-1">
            <Input
              ref={inputRef}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask Nexus anything..."
              className="pr-10 bg-secondary/50 border-border focus:border-emerald-500/50 focus:ring-emerald-500/20"
              disabled={isChatLoading}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground hover:text-foreground"
            >
              <Mic className="h-4 w-4" />
            </Button>
          </div>
          <Button
            type="submit"
            size="icon"
            className="bg-emerald-500 hover:bg-emerald-600 text-black h-10 w-10"
            disabled={!chatInput.trim() || isChatLoading}
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
        <div className="flex items-center justify-between mt-2">
          <p className="text-xs text-muted-foreground">
            <kbd className="px-1.5 py-0.5 text-[10px] bg-secondary rounded border border-border">Enter</kbd> to send
          </p>
          <Badge variant="secondary" className="text-[10px] text-muted-foreground">
            Powered by Claude
          </Badge>
        </div>
      </div>
    </aside>
  );
}
