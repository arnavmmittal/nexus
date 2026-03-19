import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Widget layout configuration
interface WidgetConfig {
  id: string;
  type: string;
  title: string;
  size: 'small' | 'medium' | 'large' | 'wide';
  visible: boolean;
  order: number;
}

// Chat message
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// Current focus session
interface FocusSession {
  task: string;
  startedAt: Date;
  duration: number; // in seconds
  isPaused: boolean;
}

interface DashboardState {
  // Layout
  widgets: WidgetConfig[];
  sidebarOpen: boolean;
  chatPanelOpen: boolean;

  // Chat
  chatMessages: ChatMessage[];
  chatInput: string;
  isChatLoading: boolean;

  // Focus
  currentFocus: FocusSession | null;

  // Actions
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setChatPanelOpen: (open: boolean) => void;
  toggleChatPanel: () => void;
  setChatInput: (input: string) => void;
  addChatMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  setChatLoading: (loading: boolean) => void;
  clearChat: () => void;
  setWidgets: (widgets: WidgetConfig[]) => void;
  updateWidget: (id: string, updates: Partial<WidgetConfig>) => void;
  reorderWidgets: (activeId: string, overId: string) => void;
  setCurrentFocus: (focus: FocusSession | null) => void;
  toggleFocusPause: () => void;
}

// Default widget configuration
const defaultWidgets: WidgetConfig[] = [
  { id: 'todays-focus', type: 'TodaysFocus', title: "Today's Focus", size: 'large', visible: true, order: 0 },
  { id: 'skill-progress', type: 'SkillProgress', title: 'Skill Progress', size: 'medium', visible: true, order: 1 },
  { id: 'money-dashboard', type: 'MoneyDashboard', title: 'Money Dashboard', size: 'large', visible: true, order: 2 },
  { id: 'goal-progress', type: 'GoalProgress', title: 'Goal Progress', size: 'large', visible: true, order: 3 },
  { id: 'health-snapshot', type: 'HealthSnapshot', title: 'Health Snapshot', size: 'wide', visible: true, order: 4 },
];

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set, get) => ({
      // Initial state
      widgets: defaultWidgets,
      sidebarOpen: true,
      chatPanelOpen: false,
      chatMessages: [],
      chatInput: '',
      isChatLoading: false,
      currentFocus: null,

      // Actions
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      setChatPanelOpen: (open) => set({ chatPanelOpen: open }),
      toggleChatPanel: () => set((state) => ({ chatPanelOpen: !state.chatPanelOpen })),

      setChatInput: (input) => set({ chatInput: input }),

      addChatMessage: (message) =>
        set((state) => ({
          chatMessages: [
            ...state.chatMessages,
            {
              ...message,
              id: crypto.randomUUID(),
              timestamp: new Date(),
            },
          ],
        })),

      setChatLoading: (loading) => set({ isChatLoading: loading }),

      clearChat: () => set({ chatMessages: [] }),

      setWidgets: (widgets) => set({ widgets }),

      updateWidget: (id, updates) =>
        set((state) => ({
          widgets: state.widgets.map((w) => (w.id === id ? { ...w, ...updates } : w)),
        })),

      reorderWidgets: (activeId, overId) =>
        set((state) => {
          const oldIndex = state.widgets.findIndex((w) => w.id === activeId);
          const newIndex = state.widgets.findIndex((w) => w.id === overId);

          if (oldIndex === -1 || newIndex === -1) return state;

          const newWidgets = [...state.widgets];
          const [removed] = newWidgets.splice(oldIndex, 1);
          newWidgets.splice(newIndex, 0, removed);

          return {
            widgets: newWidgets.map((w, i) => ({ ...w, order: i })),
          };
        }),

      setCurrentFocus: (focus) => set({ currentFocus: focus }),

      toggleFocusPause: () =>
        set((state) => ({
          currentFocus: state.currentFocus
            ? { ...state.currentFocus, isPaused: !state.currentFocus.isPaused }
            : null,
        })),
    }),
    {
      name: 'nexus-dashboard',
      partialize: (state) => ({
        widgets: state.widgets,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
);

export default useDashboardStore;
