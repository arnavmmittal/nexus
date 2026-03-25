'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Mic,
  Calendar,
  Clock,
  CloudSun,
  Bell,
  CheckCircle2,
  ChevronRight,
  Zap,
} from 'lucide-react';

// ---------- Types ----------

interface ScheduleEvent {
  id: string;
  time: string;
  title: string;
  category: 'work' | 'personal' | 'health' | 'errand';
}

interface Reminder {
  id: string;
  text: string;
  priority: 'low' | 'medium' | 'high';
  done: boolean;
}

// ---------- Mock Data ----------

const MOCK_EVENTS: ScheduleEvent[] = [
  { id: '1', time: '8:00 AM', title: 'Morning Workout', category: 'health' },
  { id: '2', time: '9:30 AM', title: 'Team Standup', category: 'work' },
  { id: '3', time: '11:00 AM', title: 'Design Review', category: 'work' },
  { id: '4', time: '12:30 PM', title: 'Lunch with Alex', category: 'personal' },
  { id: '5', time: '2:00 PM', title: 'Sprint Planning', category: 'work' },
  { id: '6', time: '4:30 PM', title: 'Pick up groceries', category: 'errand' },
  { id: '7', time: '6:00 PM', title: 'Dinner Prep', category: 'personal' },
  { id: '8', time: '8:00 PM', title: 'Read / Wind Down', category: 'personal' },
];

const MOCK_REMINDERS: Reminder[] = [
  { id: '1', text: 'Take vitamins', priority: 'high', done: false },
  { id: '2', text: 'Water the plants', priority: 'medium', done: false },
  { id: '3', text: 'Call dentist for appointment', priority: 'medium', done: false },
  { id: '4', text: 'Submit expense report', priority: 'high', done: false },
  { id: '5', text: 'Order new filters', priority: 'low', done: true },
];

// ---------- Helpers ----------

const CATEGORY_COLORS: Record<ScheduleEvent['category'], string> = {
  work: '#3b82f6',
  personal: '#10b981',
  health: '#f59e0b',
  errand: '#8b5cf6',
};

const PRIORITY_STYLES: Record<Reminder['priority'], string> = {
  high: 'border-l-red-500',
  medium: 'border-l-amber-500',
  low: 'border-l-emerald-500',
};

function getGreeting(hour: number): string {
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

// ---------- Components ----------

function DigitalClock({ time }: { time: Date }) {
  const timeStr = formatTime(time);
  const [hms, period] = timeStr.split(' ');

  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-6xl font-bold tracking-tight text-white tabular-nums sm:text-7xl lg:text-8xl">
        {hms}
      </span>
      <span className="text-2xl font-medium text-emerald-400 sm:text-3xl lg:text-4xl">
        {period}
      </span>
    </div>
  );
}

function WeatherPlaceholder() {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-white/5 bg-white/[0.03] px-5 py-3">
      <CloudSun className="h-8 w-8 text-amber-400" />
      <div>
        <p className="text-2xl font-semibold tabular-nums">72&deg;F</p>
        <p className="text-sm text-white/50">Partly Cloudy</p>
      </div>
    </div>
  );
}

function ScheduleCard({ event }: { event: ScheduleEvent }) {
  return (
    <div className="group flex items-center gap-4 rounded-2xl border border-white/5 bg-white/[0.03] px-5 py-4 transition-colors active:bg-white/[0.06]">
      <div
        className="h-12 w-1.5 flex-shrink-0 rounded-full"
        style={{ backgroundColor: CATEGORY_COLORS[event.category] }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-lg font-medium text-white sm:text-xl">
          {event.title}
        </p>
        <p className="text-base text-white/40">{event.time}</p>
      </div>
      <ChevronRight className="h-5 w-5 flex-shrink-0 text-white/20 transition-colors group-active:text-white/40" />
    </div>
  );
}

function ReminderCard({
  reminder,
  onToggle,
}: {
  reminder: Reminder;
  onToggle: (id: string) => void;
}) {
  return (
    <button
      onClick={() => onToggle(reminder.id)}
      className={`flex w-full items-center gap-4 rounded-2xl border-l-4 border border-white/5 bg-white/[0.03] px-5 py-4 text-left transition-colors active:bg-white/[0.06] ${PRIORITY_STYLES[reminder.priority]}`}
    >
      <CheckCircle2
        className={`h-7 w-7 flex-shrink-0 transition-colors ${
          reminder.done ? 'text-emerald-500' : 'text-white/20'
        }`}
      />
      <span
        className={`text-lg sm:text-xl ${
          reminder.done ? 'text-white/30 line-through' : 'text-white'
        }`}
      >
        {reminder.text}
      </span>
    </button>
  );
}

function VoiceActivationBar({ listening, onToggle }: { listening: boolean; onToggle: () => void }) {
  return (
    <div className="relative">
      {/* Glow ring behind mic when listening */}
      {listening && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-28 w-28 animate-ping rounded-full bg-emerald-500/20" />
        </div>
      )}

      <div className="flex items-center gap-5 rounded-3xl border border-white/5 bg-white/[0.03] px-6 py-4 backdrop-blur-sm">
        <button
          onClick={onToggle}
          className={`relative z-10 flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full transition-all active:scale-95 ${
            listening
              ? 'bg-emerald-500 shadow-[0_0_30px_rgba(16,185,129,0.5)]'
              : 'bg-white/10 hover:bg-white/15'
          }`}
        >
          <Mic className={`h-7 w-7 ${listening ? 'text-black' : 'text-white'}`} />
        </button>
        <div className="min-w-0 flex-1">
          <p className={`text-xl font-medium ${listening ? 'text-emerald-400' : 'text-white/50'}`}>
            {listening ? 'Listening...' : 'Hey Jarvis...'}
          </p>
          <p className="text-sm text-white/30">
            {listening ? 'Speak your command' : 'Tap to activate voice assistant'}
          </p>
        </div>
        {listening && (
          <div className="flex gap-1">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="w-1 rounded-full bg-emerald-400"
                style={{
                  height: `${16 + Math.random() * 20}px`,
                  animation: `pulse ${0.4 + i * 0.15}s ease-in-out infinite alternate`,
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusIndicator() {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
      <span className="text-xs text-white/40 uppercase tracking-widest">Online</span>
    </div>
  );
}

// ---------- Main Page ----------

export default function TerminalPage() {
  const [now, setNow] = useState<Date>(new Date());
  const [reminders, setReminders] = useState<Reminder[]>(MOCK_REMINDERS);
  const [listening, setListening] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Clock tick - every second
  useEffect(() => {
    setMounted(true);
    const clockInterval = setInterval(() => setNow(new Date()), 1_000);
    return () => clearInterval(clockInterval);
  }, []);

  // Auto-refresh data every 60 seconds (placeholder for real API calls)
  useEffect(() => {
    const refreshInterval = setInterval(() => {
      // Future: fetch real schedule, reminders, weather from Nexus API
      console.log('[Terminal] Auto-refresh triggered');
    }, 60_000);
    return () => clearInterval(refreshInterval);
  }, []);

  const toggleReminder = useCallback((id: string) => {
    setReminders((prev) =>
      prev.map((r) => (r.id === id ? { ...r, done: !r.done } : r))
    );
  }, []);

  const toggleListening = useCallback(() => {
    setListening((prev) => !prev);
  }, []);

  // Avoid hydration mismatch for time-dependent content
  if (!mounted) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#0a0a0a]">
        <Zap className="h-12 w-12 animate-pulse text-emerald-500" />
      </div>
    );
  }

  const greeting = getGreeting(now.getHours());
  const dateStr = formatDate(now);
  const pendingReminders = reminders.filter((r) => !r.done).length;

  return (
    <div className="flex h-screen w-full flex-col bg-[#0a0a0a] p-4 sm:p-6 lg:p-8">
      {/* ===== HEADER ===== */}
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between lg:mb-8">
        <div className="space-y-1">
          <DigitalClock time={now} />
          <p className="text-lg text-white/50 sm:text-xl">{dateStr}</p>
        </div>
        <div className="flex items-center gap-4">
          <WeatherPlaceholder />
          <StatusIndicator />
        </div>
      </header>

      {/* Greeting */}
      <div className="mb-6 lg:mb-8">
        <h1 className="text-3xl font-bold text-white sm:text-4xl">
          {greeting},{' '}
          <span className="text-gradient-green">Arnav</span>
        </h1>
        <p className="mt-1 text-base text-white/40 sm:text-lg">
          {pendingReminders > 0
            ? `You have ${pendingReminders} pending reminder${pendingReminders > 1 ? 's' : ''} today.`
            : 'All caught up. Enjoy your day.'}
        </p>
      </div>

      {/* ===== MAIN CONTENT GRID ===== */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-5 lg:gap-6">
        {/* Schedule - takes more space */}
        <section className="flex min-h-0 flex-col lg:col-span-3">
          <div className="mb-3 flex items-center gap-2">
            <Calendar className="h-5 w-5 text-emerald-500" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-white/50">
              Today&apos;s Schedule
            </h2>
            <span className="ml-auto rounded-full bg-white/5 px-3 py-0.5 text-xs text-white/40 tabular-nums">
              {MOCK_EVENTS.length} events
            </span>
          </div>
          <div className="custom-scrollbar flex-1 space-y-2 overflow-y-auto pr-1">
            {MOCK_EVENTS.map((event) => (
              <ScheduleCard key={event.id} event={event} />
            ))}
          </div>
        </section>

        {/* Reminders */}
        <section className="flex min-h-0 flex-col lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <Bell className="h-5 w-5 text-amber-400" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-white/50">
              Reminders
            </h2>
            <span className="ml-auto rounded-full bg-white/5 px-3 py-0.5 text-xs text-white/40 tabular-nums">
              {pendingReminders} pending
            </span>
          </div>
          <div className="custom-scrollbar flex-1 space-y-2 overflow-y-auto pr-1">
            {reminders.map((reminder) => (
              <ReminderCard
                key={reminder.id}
                reminder={reminder}
                onToggle={toggleReminder}
              />
            ))}
          </div>
        </section>
      </div>

      {/* ===== VOICE ACTIVATION BAR ===== */}
      <footer className="mt-4 sm:mt-6">
        <VoiceActivationBar listening={listening} onToggle={toggleListening} />
      </footer>
    </div>
  );
}
