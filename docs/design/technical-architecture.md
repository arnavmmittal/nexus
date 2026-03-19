# Nexus Technical Architecture

## Overview

Nexus is a full-stack application with a Next.js frontend, Python backend for AI/ML, and multiple data stores for different purposes.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│                           (Next.js 14+)                                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Widgets    │  │   AI Chat    │  │   Settings   │  │   Analytics  │ │
│  │   Dashboard  │  │   Interface  │  │   Panel      │  │   Views      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API LAYER                                     │
│                      (FastAPI + WebSocket)                               │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  /api/chat   │  │ /api/widgets │  │ /api/memory  │  │ /api/skills  │ │
│  │              │  │              │  │              │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   AI ENGINE      │  │   MEMORY LAYER   │  │   INTEGRATIONS   │
│                  │  │                  │  │                  │
│  Claude API      │  │  PostgreSQL      │  │  Google Cal      │
│  Context Builder │  │  ChromaDB        │  │  Apple Health    │
│  Memory Search   │  │  Obsidian Sync   │  │  GitHub          │
│                  │  │                  │  │  Plaid (Finance) │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Tech Stack

### Frontend
| Layer | Technology | Purpose |
|-------|------------|---------|
| Framework | Next.js 14+ (App Router) | React with SSR/SSG |
| Styling | Tailwind CSS + shadcn/ui | Dark mode, components |
| State | Zustand | Client state management |
| Data Fetching | TanStack Query | Server state, caching |
| Charts | Recharts / Tremor | Data visualization |
| Drag & Drop | dnd-kit | Widget arrangement |
| Real-time | Socket.io client | Live updates |

### Backend
| Layer | Technology | Purpose |
|-------|------------|---------|
| API Framework | FastAPI | Async Python API |
| WebSocket | FastAPI WebSocket | Real-time chat |
| AI | Anthropic SDK (Claude) | Conversational AI |
| Embeddings | OpenAI / Ollama | Vector embeddings |
| Task Queue | Celery + Redis | Background jobs |
| Cron | APScheduler | Scheduled tasks |

### Data Stores
| Store | Technology | Purpose |
|-------|------------|---------|
| Primary DB | PostgreSQL | Structured data |
| Vector DB | ChromaDB | Semantic search |
| Cache | Redis | Sessions, caching |
| File Storage | Local filesystem | Obsidian vault, exports |

### Integrations
| Service | API/Method | Data |
|---------|------------|------|
| Google Calendar | OAuth + API | Schedule |
| Apple Health | HealthKit export | Fitness data |
| GitHub | OAuth + API | Commits, activity |
| Plaid | API | Bank, investments |
| Claude History | Local JSONL | Conversation sync |

---

## Project Structure

```
nexus/
├── frontend/                    # Next.js application
│   ├── app/
│   │   ├── (dashboard)/        # Main dashboard routes
│   │   │   ├── page.tsx        # Dashboard home
│   │   │   ├── goals/          # Goals page
│   │   │   ├── skills/         # Skills page
│   │   │   └── settings/       # Settings page
│   │   ├── api/                # Next.js API routes (if needed)
│   │   └── layout.tsx          # Root layout
│   ├── components/
│   │   ├── widgets/            # Widget components
│   │   │   ├── TodaysFocus.tsx
│   │   │   ├── MoneyDashboard.tsx
│   │   │   ├── SkillProgress.tsx
│   │   │   ├── HealthSnapshot.tsx
│   │   │   └── GoalProgress.tsx
│   │   ├── chat/               # AI chat interface
│   │   ├── layout/             # Layout components
│   │   └── ui/                 # Base UI components
│   ├── lib/
│   │   ├── api.ts              # API client
│   │   ├── socket.ts           # WebSocket client
│   │   └── utils.ts            # Utilities
│   ├── stores/                 # Zustand stores
│   └── styles/                 # Global styles
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py             # FastAPI app entry
│   │   ├── api/
│   │   │   ├── chat.py         # Chat endpoints
│   │   │   ├── widgets.py      # Widget data endpoints
│   │   │   ├── memory.py       # Memory CRUD
│   │   │   ├── skills.py       # Skill tracking
│   │   │   └── goals.py        # Goal management
│   │   ├── core/
│   │   │   ├── config.py       # Configuration
│   │   │   ├── security.py     # Auth (if needed)
│   │   │   └── database.py     # DB connection
│   │   ├── ai/
│   │   │   ├── engine.py       # Claude integration
│   │   │   ├── context.py      # Context assembly
│   │   │   ├── memory.py       # Memory retrieval
│   │   │   └── prompts.py      # System prompts
│   │   ├── memory/
│   │   │   ├── vector_store.py # ChromaDB operations
│   │   │   ├── obsidian.py     # Obsidian sync
│   │   │   └── claude_sync.py  # Claude history import
│   │   ├── integrations/
│   │   │   ├── google_cal.py   # Google Calendar
│   │   │   ├── apple_health.py # Apple Health
│   │   │   ├── github.py       # GitHub
│   │   │   └── plaid.py        # Financial data
│   │   ├── models/
│   │   │   ├── user.py         # User model
│   │   │   ├── skill.py        # Skill models
│   │   │   ├── goal.py         # Goal models
│   │   │   └── memory.py       # Memory models
│   │   └── services/
│   │       ├── skill_tracker.py
│   │       ├── goal_tracker.py
│   │       └── pattern_detector.py
│   ├── alembic/                # Database migrations
│   └── tests/                  # Backend tests
│
├── data/                        # Local data storage
│   ├── obsidian/               # Obsidian vault (symlink)
│   ├── vectors/                # ChromaDB storage
│   └── exports/                # Data exports
│
├── docs/                        # Documentation
│   └── design/                 # Design documents
│
├── docker-compose.yml          # Local dev environment
├── .env.example                # Environment template
└── README.md                   # Project readme
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- User (single user system, but structured for future)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255),
    email VARCHAR(255),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Facts (explicit knowledge about user)
CREATE TABLE facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    category VARCHAR(50),  -- 'goal', 'preference', 'value', 'identity'
    key VARCHAR(255),
    value TEXT,
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Patterns (learned behaviors)
CREATE TABLE patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    domain VARCHAR(50),
    pattern_type VARCHAR(100),
    description TEXT,
    evidence JSONB,
    confidence FLOAT,
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skills
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255),
    category VARCHAR(100),
    current_level INT DEFAULT 1,
    current_xp INT DEFAULT 0,
    total_xp INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_practiced TIMESTAMPTZ,
    UNIQUE(user_id, name)
);

-- Skill XP Log
CREATE TABLE skill_xp_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id),
    xp_amount INT,
    source VARCHAR(100),  -- 'claude_session', 'manual', 'integration'
    description TEXT,
    logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- Goals
CREATE TABLE goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    domain VARCHAR(50),
    target_type VARCHAR(50),  -- 'numeric', 'boolean', 'streak'
    target_value FLOAT,
    current_value FLOAT DEFAULT 0,
    unit VARCHAR(50),
    deadline DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Goal Progress Log
CREATE TABLE goal_progress_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID REFERENCES goals(id),
    previous_value FLOAT,
    new_value FLOAT,
    logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations (for memory)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    source VARCHAR(50),  -- 'nexus', 'claude_code', 'claude_web'
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    summary TEXT,
    extracted_facts JSONB,
    extracted_skills JSONB
);

-- Streaks
CREATE TABLE streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    activity VARCHAR(255),
    current_count INT DEFAULT 0,
    longest_count INT DEFAULT 0,
    last_logged DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Achievements
CREATE TABLE achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    achievement_key VARCHAR(100),
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, achievement_key)
);
```

---

## API Endpoints

### Chat
```
POST   /api/chat              # Send message, get response
GET    /api/chat/history      # Get conversation history
WS     /api/chat/stream       # Streaming responses
```

### Widgets
```
GET    /api/widgets/today     # Today's focus data
GET    /api/widgets/money     # Financial data
GET    /api/widgets/skills    # Skill progress
GET    /api/widgets/health    # Health data
GET    /api/widgets/goals     # Goal progress
```

### Skills
```
GET    /api/skills            # List all skills
POST   /api/skills            # Create skill
GET    /api/skills/:id        # Get skill detail
POST   /api/skills/:id/log    # Log XP
GET    /api/skills/:id/history # XP history
```

### Goals
```
GET    /api/goals             # List goals
POST   /api/goals             # Create goal
PATCH  /api/goals/:id         # Update goal
POST   /api/goals/:id/progress # Log progress
```

### Memory
```
GET    /api/memory/search     # Semantic search
GET    /api/memory/facts      # List facts
POST   /api/memory/facts      # Add fact
GET    /api/memory/patterns   # List patterns
POST   /api/memory/sync       # Sync Claude history
```

### Integrations
```
POST   /api/integrations/google/connect
POST   /api/integrations/github/connect
POST   /api/integrations/plaid/connect
GET    /api/integrations/status
```

---

## Real-time Updates

### WebSocket Events

```typescript
// Client → Server
{ type: 'chat_message', content: string }
{ type: 'subscribe_widget', widget: string }
{ type: 'unsubscribe_widget', widget: string }

// Server → Client
{ type: 'chat_response', content: string, done: boolean }
{ type: 'widget_update', widget: string, data: object }
{ type: 'notification', title: string, body: string }
{ type: 'achievement_unlocked', achievement: object }
```

---

## AI Engine Details

### Context Assembly Pipeline

```python
async def assemble_context(query: str, user_id: str) -> str:
    context = []

    # 1. Load identity (always)
    identity = await get_user_identity(user_id)
    context.append(format_identity(identity))

    # 2. Load current state
    state = await get_current_state(user_id)
    context.append(format_state(state))

    # 3. Semantic search for relevant memory
    relevant = await vector_search(query, user_id, limit=5)
    context.append(format_memories(relevant))

    # 4. Domain-specific context
    domain = classify_query(query)
    domain_context = await get_domain_context(domain, user_id)
    context.append(format_domain(domain_context))

    return "\n\n".join(context)
```

### Claude System Prompt

```python
SYSTEM_PROMPT = """
You are Nexus, a personal AI assistant for {user_name}.

## Your Role
You are like JARVIS for Tony Stark - a trusted companion who knows
{user_name} deeply and helps them optimize their life.

## What You Know
{assembled_context}

## Communication Style
- Be direct and actionable
- Make confident recommendations
- Celebrate wins
- Be honest about problems
- Match {user_name}'s preferred level of detail

## Capabilities
- Access to all life domains: money, learning, health, time
- Can log skills, update goals, set focus tasks
- Remember everything - reference past conversations naturally
- Proactively surface relevant information

## Guidelines
- Never make up data - if you don't know, say so
- When suggesting actions, be specific
- Reference past context naturally ("as we discussed...")
- If asked about something you can't do, suggest alternatives
"""
```

---

## Development Setup

```bash
# Clone
git clone https://github.com/arnavmmittal/nexus
cd nexus

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure API keys
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev

# Database
docker-compose up -d postgres redis chromadb
alembic upgrade head
```

---

## Environment Variables

```bash
# AI
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # For embeddings (optional)

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/nexus
REDIS_URL=redis://localhost:6379

# Integrations
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_TOKEN=...
PLAID_CLIENT_ID=...
PLAID_SECRET=...

# Paths
OBSIDIAN_VAULT_PATH=/path/to/vault
CLAUDE_HISTORY_PATH=~/.claude/projects
```

---

*Last updated: 2026-03-19*
