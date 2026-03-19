# Nexus Memory Architecture

## The "Never Forget" System

### Overview

Nexus maintains persistent memory through three integrated systems:

```
┌─────────────────────────────────────────────────────────────────┐
│                      NEXUS MEMORY LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  OBSIDIAN   │  │   VECTOR    │  │    STRUCTURED DB        │ │
│  │  VAULT      │  │   STORE     │  │    (PostgreSQL)         │ │
│  │             │  │             │  │                         │ │
│  │  Markdown   │  │  Embeddings │  │  Facts, goals, prefs    │ │
│  │  notes,     │  │  for        │  │  Patterns, streaks      │ │
│  │  journals,  │  │  semantic   │  │  Skills, XP, levels     │ │
│  │  learnings  │  │  search     │  │  Integration data       │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                      │               │
│         └────────────────┼──────────────────────┘               │
│                          │                                      │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │   CONTEXT ASSEMBLER   │                          │
│              │                       │                          │
│              │  Builds relevant      │                          │
│              │  context for each     │                          │
│              │  AI interaction       │                          │
│              └───────────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Obsidian Vault Integration

### Why Obsidian?
- **Free** for personal use
- **Local-first** - your data stays on your machine
- **Markdown** - simple, portable, version-controllable
- **Knowledge graph** - links between notes create relationships
- **Plugin ecosystem** - extensible

### What Lives in Obsidian
```
vault/
├── daily/              # Daily notes, journals
│   ├── 2026-03-19.md
│   └── ...
├── learnings/          # What you've learned
│   ├── python/
│   ├── ai-ml/
│   └── business/
├── projects/           # Project notes
│   ├── youtube-automation.md
│   ├── tiktok-automation.md
│   └── nexus.md
├── people/             # People you interact with
├── decisions/          # Major decisions + reasoning
└── me/                 # Self-knowledge
    ├── goals.md
    ├── values.md
    ├── preferences.md
    └── patterns.md
```

### Sync Strategy
- Nexus watches the Obsidian vault directory
- Changes trigger re-indexing
- Bi-directional: Nexus can also write notes (e.g., from Claude sessions)

---

## 2. Vector Store (Semantic Search)

### Purpose
Enable natural language queries across all your knowledge:
- "What did I learn about async Python?"
- "What was my reasoning for choosing Next.js?"
- "Show me everything about my morning routine experiments"

### Implementation
- **Embedding model:** OpenAI text-embedding-3-small or local (Ollama)
- **Vector DB:** ChromaDB (local, simple) or Pinecone (cloud, scalable)
- **Indexed content:**
  - All Obsidian notes
  - Claude conversation history
  - Project READMEs and docs
  - Journal entries

### Chunking Strategy
- Split documents into ~500 token chunks
- Preserve context (include headers, metadata)
- Store source reference for retrieval

---

## 3. Structured Database (PostgreSQL)

### Purpose
Store structured data that needs querying, relationships, and fast lookups.

### Schema Overview

```sql
-- Core identity
CREATE TABLE user_profile (
    id UUID PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP,
    settings JSONB
);

-- Explicit facts ("I want to be a billionaire")
CREATE TABLE facts (
    id UUID PRIMARY KEY,
    category TEXT,  -- 'goal', 'preference', 'value', 'identity'
    content TEXT,
    confidence FLOAT,  -- how sure are we this is still true
    source TEXT,  -- where did this come from
    created_at TIMESTAMP,
    last_confirmed TIMESTAMP
);

-- Learned patterns ("You're most productive at 9am")
CREATE TABLE patterns (
    id UUID PRIMARY KEY,
    domain TEXT,  -- 'productivity', 'health', 'mood'
    pattern TEXT,
    evidence JSONB,  -- data points supporting this
    strength FLOAT,  -- how confident
    discovered_at TIMESTAMP
);

-- Skills (both digital and real-life)
CREATE TABLE skills (
    id UUID PRIMARY KEY,
    name TEXT,
    category TEXT,  -- 'programming', 'physical', 'creative', 'business'
    current_level INT,
    xp INT,
    started_at TIMESTAMP,
    last_practiced TIMESTAMP,
    notes TEXT
);

-- Skill progress entries
CREATE TABLE skill_progress (
    id UUID PRIMARY KEY,
    skill_id UUID REFERENCES skills(id),
    xp_gained INT,
    activity TEXT,
    source TEXT,  -- 'claude_session', 'manual', 'integration'
    timestamp TIMESTAMP
);

-- Goals with progress tracking
CREATE TABLE goals (
    id UUID PRIMARY KEY,
    title TEXT,
    domain TEXT,  -- 'money', 'learning', 'health', 'time'
    target_value FLOAT,
    current_value FLOAT,
    unit TEXT,
    deadline TIMESTAMP,
    status TEXT,  -- 'active', 'completed', 'abandoned'
    created_at TIMESTAMP
);
```

---

## 4. Claude Conversation Sync

### Sources
1. **Claude Code sessions** - Local JSONL files in `~/.claude/`
2. **Claude.ai conversations** - If API access available
3. **Manual imports** - Paste conversations

### Extraction Pipeline

```
Claude Session
     │
     ▼
┌─────────────────────┐
│  PARSER             │
│  Extract messages,  │
│  code, decisions    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ANALYZER           │
│  Identify learnings,│
│  skills practiced,  │
│  patterns           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  INDEXER            │
│  Create embeddings, │
│  store in vector DB │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  UPDATER            │
│  Update skills XP,  │
│  facts, patterns    │
└─────────────────────┘
```

### What Gets Extracted
- **Skills practiced:** "Worked on Python async" → +XP to Python skill
- **Decisions made:** "Chose FastAPI over Flask" → stored with reasoning
- **Learnings:** Key insights, techniques, patterns
- **Projects worked on:** Link to project records
- **Problems solved:** For future reference

---

## 5. Context Assembly

When you interact with Nexus AI, it assembles relevant context:

```python
def assemble_context(query: str) -> str:
    context_parts = []

    # 1. Core identity (always included)
    context_parts.append(get_user_profile())
    context_parts.append(get_active_goals())

    # 2. Semantic search for relevant memories
    relevant_notes = vector_search(query, limit=5)
    context_parts.extend(relevant_notes)

    # 3. Recent context (last 24 hours)
    context_parts.append(get_recent_activity())

    # 4. Domain-specific context
    domain = classify_query_domain(query)
    if domain == "learning":
        context_parts.append(get_skill_progress())
        context_parts.append(get_recent_learnings())
    elif domain == "productivity":
        context_parts.append(get_productivity_patterns())
        context_parts.append(get_todays_schedule())
    # ... etc

    return compile_context(context_parts)
```

---

## Privacy & Security

- **Local-first:** All data stored on your machine by default
- **Encrypted at rest:** Database and vault can be encrypted
- **No cloud sync required:** Works fully offline
- **Optional sync:** Can enable cloud backup if desired
- **You own your data:** Standard formats (Markdown, PostgreSQL)

---

*Last updated: 2026-03-19*
