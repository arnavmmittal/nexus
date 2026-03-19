# Nexus Widget System

## Overview

Widgets are the visual building blocks of your dashboard. Each widget is a self-contained component that displays specific information and can be arranged in a customizable grid.

---

## Core Widgets

### 1. Today's Focus

**Purpose:** Keep you locked in on what matters today.

```
┌─────────────────────────────────────────────────────────────┐
│  ☀️  TODAY'S FOCUS                          Wed, Mar 19     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🎯 TOP 3 PRIORITIES                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. [█████████░] Finish Nexus design docs            │   │
│  │ 2. [ ] Generate 5 TikTok videos                     │   │
│  │ 3. [ ] Review investment portfolio                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ⏱️ CURRENT FOCUS                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Working on: Nexus design                           │   │
│  │  ████████████████░░░░  45:22 elapsed                │   │
│  │                                                     │   │
│  │  [Pause]  [Complete]  [Switch Task]                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  📊 Today: 3h 22m deep work  •  2 tasks completed          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Data Sources:**
- Manual input (set priorities each morning)
- Calendar integration (meetings/blocks)
- Task manager integration (Todoist, Notion)

---

### 2. Money Dashboard

**Purpose:** Complete financial snapshot at a glance.

```
┌─────────────────────────────────────────────────────────────┐
│  💰 MONEY DASHBOARD                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  NET WORTH                            MONTHLY INCOME        │
│  ┌─────────────────────┐              ┌─────────────────┐  │
│  │    $47,832          │              │    $4,250       │  │
│  │    ▲ $1,204 (2.5%)  │              │    ▲ $800       │  │
│  │    this month       │              │    vs last mo   │  │
│  └─────────────────────┘              └─────────────────┘  │
│                                                             │
│  PORTFOLIO                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Stocks    $28,400  ████████████████░░░░  ▲ 3.2%    │   │
│  │  Crypto    $8,200   █████░░░░░░░░░░░░░░░  ▼ 1.8%    │   │
│  │  Cash      $11,232  ███████░░░░░░░░░░░░░  ─ 0.0%    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  INCOME STREAMS                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  💼 Freelance    $2,500  ████████████░░░░░░░░       │   │
│  │  📺 YouTube      $450    ██░░░░░░░░░░░░░░░░░░       │   │
│  │  🎵 TikTok       $120    █░░░░░░░░░░░░░░░░░░░       │   │
│  │  📈 Dividends    $180    █░░░░░░░░░░░░░░░░░░░       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Data Sources:**
- Plaid API (bank accounts, investments)
- Robinhood/Coinbase APIs
- Manual income logging
- Stripe (if selling products)

---

### 3. Skill Progress

**Purpose:** Visualize your growth and maintain streaks.

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ SKILL PROGRESS                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TODAY'S XP                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          +385 XP                                    │   │
│  │  ████████████████████████░░░░░░  385/500 daily goal │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  SKILLS PRACTICED                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  🐍 Python         +125 XP    Lv.8 → 62% to Lv.9   │   │
│  │  🎨 UI Design      +80 XP     Lv.4 → 45% to Lv.5   │   │
│  │  📊 Data Analysis  +50 XP     Lv.3 → 78% to Lv.4   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  🔥 ACTIVE STREAKS                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Coding         23 days 🔥     Gym        8 days   │   │
│  │  Reading        15 days 📚     Meditation 3 days   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  🏆 RECENT ACHIEVEMENT: "Week Warrior" - 7 day coding streak│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Data Sources:**
- Claude session analysis (automatic)
- GitHub activity
- Manual skill logs
- Integration with learning platforms

---

### 4. Health Snapshot

**Purpose:** Body and energy awareness.

```
┌─────────────────────────────────────────────────────────────┐
│  💪 HEALTH SNAPSHOT                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   SLEEP     │ │   ENERGY    │ │   WORKOUT   │           │
│  │    7.2h     │ │    ████░    │ │   ✓ Done    │           │
│  │   ⭐ 82/100 │ │    High     │ │   Push Day  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                             │
│  WEEKLY OVERVIEW                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │       M    T    W    T    F    S    S               │   │
│  │ Sleep ██   ███  ██   ██   ░░   ░░   ░░              │   │
│  │ Gym   ✓    ─    ✓    ─    ░░   ░░   ░░              │   │
│  │ Steps 8k   12k  6k   9k   ░░   ░░   ░░              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  📈 TREND: Sleep quality up 12% vs last week               │
│  💡 INSIGHT: Best energy on days after 7+ hour sleep       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Data Sources:**
- Apple Health / Google Fit
- Oura Ring / Whoop (if available)
- Manual mood/energy logging
- Gym app integrations

---

### 5. Goal Progress (OKR Style)

**Purpose:** Long-term goals with numerical progress tracking.

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 GOAL PROGRESS                                   Q1 2026 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  💰 FINANCIAL                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Net Worth: $100K                                   │   │
│  │  [██████████████░░░░░░░░░░░░░░░░] $47,832 (47.8%)   │   │
│  │                                                     │   │
│  │  Monthly Income: $10K/mo                            │   │
│  │  [█████████░░░░░░░░░░░░░░░░░░░░░] $4,250 (42.5%)    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  📚 LEARNING                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Python Mastery: Level 15                           │   │
│  │  [████████████████░░░░░░░░░░░░░░] Lv.8 (53%)        │   │
│  │                                                     │   │
│  │  Ship 5 Projects                                    │   │
│  │  [████████████░░░░░░░░░░░░░░░░░░] 3/5 (60%)         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  💪 FITNESS                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Bench Press: 225 lbs                               │   │
│  │  [████████████████████░░░░░░░░░░] 185 lbs (82%)     │   │
│  │                                                     │   │
│  │  Run 5K under 25 min                                │   │
│  │  [██████████████░░░░░░░░░░░░░░░░] 28 min (89%)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ⏱️ TIME                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Deep Work: 100 hrs/month                           │   │
│  │  [██████████████████████░░░░░░░░] 68 hrs (68%)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Data Sources:**
- Aggregated from other widgets
- Manual goal setting
- Auto-calculated from integrations

---

## Secondary Widgets

### Calendar / Schedule
```
┌─────────────────────────────────────┐
│  📅 TODAY                           │
├─────────────────────────────────────┤
│  09:00  ████  Deep Work Block       │
│  12:00  ██    Lunch                 │
│  14:00  ███   Team Call             │
│  16:00  ████  Deep Work Block       │
│  18:00  ██    Gym                   │
└─────────────────────────────────────┘
```

### AI Chat (Mini)
```
┌─────────────────────────────────────┐
│  🤖 NEXUS AI                        │
├─────────────────────────────────────┤
│  "Good morning! You have 3 focus    │
│   tasks today. Your energy pattern  │
│   suggests tackling the hardest     │
│   one (Nexus design) first.         │
│                                     │
│   You're on a 23-day coding streak  │
│   - keep it going!"                 │
│                                     │
│  [Ask Nexus...]                     │
└─────────────────────────────────────┘
```

### Quick Actions
```
┌─────────────────────────────────────┐
│  ⚡ QUICK ACTIONS                   │
├─────────────────────────────────────┤
│  [+ Log Workout]  [+ Log Skill]    │
│  [+ Add Task]     [+ Quick Note]   │
│  [🍅 Pomodoro]    [📝 Journal]     │
└─────────────────────────────────────┘
```

### Habits Tracker
```
┌─────────────────────────────────────┐
│  ✅ DAILY HABITS                    │
├─────────────────────────────────────┤
│  [✓] Morning routine                │
│  [✓] Workout                        │
│  [ ] Read 30 min                    │
│  [ ] Meditate                       │
│  [✓] Deep work 4+ hrs              │
│  [ ] Journal                        │
└─────────────────────────────────────┘
```

---

## Widget Grid System

### Layout Options

**Default (3-column)**
```
┌────────────────┬────────────────┬────────────────┐
│  Today's       │  Skill         │  Calendar      │
│  Focus         │  Progress      │                │
│  (large)       │  (medium)      │  (medium)      │
├────────────────┼────────────────┼────────────────┤
│  Money         │  Goal          │  Quick         │
│  Dashboard     │  Progress      │  Actions       │
│  (large)       │  (large)       │  (small)       │
├────────────────┴────────────────┼────────────────┤
│  Health Snapshot                │  AI Chat       │
│  (wide)                         │  (medium)      │
└─────────────────────────────────┴────────────────┘
```

### Customization
- Drag and drop to rearrange
- Resize widgets (small, medium, large, wide)
- Hide/show widgets
- Save multiple layouts (Focus Mode, Review Mode, etc.)

---

## Widget States

### Loading
```
┌─────────────────────┐
│  ░░░░░░░░░░░░░░░░░ │
│  Loading data...    │
└─────────────────────┘
```

### Error
```
┌─────────────────────┐
│  ⚠️ Connection lost │
│  [Retry]            │
└─────────────────────┘
```

### Empty
```
┌─────────────────────┐
│  No data yet        │
│  [Set up integration│
│   or log manually]  │
└─────────────────────┘
```

---

## Interaction Patterns

### Hover
- Show additional details
- Reveal action buttons
- Highlight related data

### Click
- Expand to full view
- Open detail modal
- Navigate to dedicated page

### Right-Click
- Widget settings
- Refresh data
- Hide widget

---

*Last updated: 2026-03-19*
