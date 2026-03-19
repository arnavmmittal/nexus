# Nexus - Personal Life Operating System

> Your AI-powered JARVIS that knows you, learns you, and never forgets.

## Core Vision

Nexus is not just a dashboard - it's a **persistent AI companion** that accumulates knowledge about you over time. Unlike traditional LLMs that forget after each session, Nexus maintains a comprehensive "memory layer" that captures:

- Your goals, values, and priorities
- Patterns in your behavior and productivity
- Skills you're developing (both digital and real-life)
- Conversations and insights from Claude sessions
- Your preferences, quirks, and decision-making style

**The goal:** An AI that knows you as well as a close friend or executive assistant who's worked with you for years.

---

## Design Decisions

### Target User
- Primary: Arnav (single-user system, deeply personalized)
- Platform: Desktop browser (ambient second-monitor use)

### Four Life Domains
| Domain | Color | Examples |
|--------|-------|----------|
| Money & Business | Emerald (#10b981) | Income streams, investments, projects, content monetization |
| Learning & Growth | Blue (#3b82f6) | Skills, courses, Claude conversations, knowledge base |
| Health & Energy | Orange (#f59e0b) | Sleep, exercise, nutrition, energy patterns |
| Time & Focus | Purple (#8b5cf6) | Calendar, deep work, tasks, focus sessions |

### Data Strategy
- **Integration Hub:** Pulls from Google Calendar, Notion, GitHub, Apple Health, Robinhood, etc.
- **Memory Layer:** Persistent vector database storing everything about the user
- **Claude Sync:** Imports and indexes Claude conversation history

### Core Features
1. **AI Command Center** - Chat interface with full context about you
2. **Ambient Display** - Always-on widgets for second monitor
3. **Gamified Progress** - XP, levels, streaks, achievements
4. **Predictive Intelligence** - Pattern detection and personalized insights

---

## Visual Identity

### Color Palette
```
Background:     #0a0a0a (OLED black)
Surface:        #141414 (cards)
Surface Hover:  #1f1f1f
Border:         #2a2a2a
Text Primary:   #ffffff
Text Secondary: #a1a1a1
Text Muted:     #6b6b6b

Accent Green:   #10b981 (Money)
Accent Blue:    #3b82f6 (Learning)
Accent Orange:  #f59e0b (Health)
Accent Purple:  #8b5cf6 (Time)
```

### Typography
- **UI:** Inter (clean, readable)
- **Numbers/Stats:** JetBrains Mono (monospace, technical feel)
- **Headings:** Inter Bold or Geist

### Visual Style
- Glassmorphism panels with subtle backdrop blur
- Animated gradient mesh background (very subtle)
- Smooth 60fps transitions
- Satisfying micro-interactions (hover states, clicks)
- Premium trading terminal meets sci-fi command deck

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Nexus                                    [Search] [Settings]│
├──────────┬──────────────────────────────────┬───────────────┤
│          │                                  │               │
│  NAV     │     MAIN WIDGET GRID             │  TODAY        │
│          │     (customizable)               │  SCHEDULE     │
│  ──────  │                                  │               │
│          │  ┌────────┐ ┌────────┐          │  ───────────  │
│  AI CHAT │  │ Widget │ │ Widget │          │               │
│  PANEL   │  └────────┘ └────────┘          │  QUICK        │
│          │  ┌────────┐ ┌────────┐          │  ACTIONS      │
│  (expand │  │ Widget │ │ Widget │          │               │
│   able)  │  └────────┘ └────────┘          │               │
│          │                                  │               │
└──────────┴──────────────────────────────────┴───────────────┘
```

---

## The Memory Problem (Key Innovation)

### Why LLMs Forget
Traditional LLMs have no persistent memory. Each conversation starts fresh. Even with context windows, they can't truly "know" you over months/years.

### Nexus Solution: Personal Knowledge Graph + Vector Memory

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS MEMORY LAYER                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  FACTS      │    │  PATTERNS   │    │  CONTEXT    │     │
│  │  Database   │    │  Engine     │    │  Vector DB  │     │
│  ├─────────────┤    ├─────────────┤    ├─────────────┤     │
│  │ Name: Arnav │    │ Productive  │    │ Embeddings  │     │
│  │ Goal: $1B   │    │ at 9-11am   │    │ of all      │     │
│  │ Learning:   │    │ Energy dips │    │ conversations│    │
│  │  Python,    │    │ after lunch │    │ decisions,  │     │
│  │  AI/ML      │    │ Best gym:   │    │ preferences │     │
│  │ Projects:   │    │  morning    │    │             │     │
│  │  YouTube,   │    │             │    │             │     │
│  │  TikTok     │    │             │    │             │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 CLAUDE CONVERSATION SYNC                 ││
│  │  Imports Claude Code sessions, extracts learnings,       ││
│  │  indexes decisions, builds understanding over time       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### What Gets Remembered
1. **Explicit facts** - Things you tell it ("I want to be a billionaire")
2. **Inferred patterns** - Things it learns ("You work best in mornings")
3. **Conversation history** - Indexed and searchable Claude sessions
4. **Decisions & reasoning** - Why you chose X over Y
5. **Skills & progress** - What you're learning, how far you've come
6. **Preferences** - Communication style, level of detail wanted

---

## Next Steps (To Design)

1. Memory architecture - How exactly to store and retrieve personal context
2. Integration layer - Which services to connect first
3. Widget system - What widgets exist, how to customize
4. AI interaction model - How the chat interface works
5. Gamification system - XP, levels, achievements
6. Skill tracking - Digital + real-life skills

---

*Design started: 2026-03-19*
*Status: In Progress*
