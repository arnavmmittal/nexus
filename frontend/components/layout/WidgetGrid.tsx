'use client';

import { useDashboardStore } from '@/stores/dashboard';
import { cn } from '@/lib/utils';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

// Widget imports
import { TodaysFocus } from '@/components/widgets/TodaysFocus';
import { MoneyDashboard } from '@/components/widgets/MoneyDashboard';
import { SkillProgress } from '@/components/widgets/SkillProgress';
import { HealthSnapshot } from '@/components/widgets/HealthSnapshot';
import { GoalProgress } from '@/components/widgets/GoalProgress';

// Widget type to component mapping
const widgetComponents: Record<string, React.ComponentType> = {
  TodaysFocus,
  MoneyDashboard,
  SkillProgress,
  HealthSnapshot,
  GoalProgress,
};

interface SortableWidgetProps {
  id: string;
  type: string;
  size: 'small' | 'medium' | 'large' | 'wide';
}

function SortableWidget({ id, type, size }: SortableWidgetProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const WidgetComponent = widgetComponents[type];

  if (!WidgetComponent) {
    return null;
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'transition-shadow duration-200',
        isDragging && 'z-50 shadow-2xl opacity-90',
        // Grid column spans based on size
        size === 'small' && 'col-span-1',
        size === 'medium' && 'col-span-1 lg:col-span-1',
        size === 'large' && 'col-span-1 lg:col-span-2',
        size === 'wide' && 'col-span-1 lg:col-span-2 xl:col-span-3'
      )}
      {...attributes}
      {...listeners}
    >
      <WidgetComponent />
    </div>
  );
}

export function WidgetGrid() {
  const { widgets, reorderWidgets, sidebarOpen, chatPanelOpen } = useDashboardStore();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      reorderWidgets(active.id as string, over.id as string);
    }
  };

  const visibleWidgets = widgets
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order);

  return (
    <main
      className={cn(
        'min-h-screen pt-16 transition-all duration-300',
        sidebarOpen ? 'pl-56' : 'pl-16',
        chatPanelOpen ? 'pr-96' : 'pr-0'
      )}
    >
      <div className="p-6 gradient-mesh min-h-[calc(100vh-4rem)]">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={visibleWidgets.map((w) => w.id)} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-min">
              {visibleWidgets.map((widget) => (
                <SortableWidget
                  key={widget.id}
                  id={widget.id}
                  type={widget.type}
                  size={widget.size}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>
    </main>
  );
}
