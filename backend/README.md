# Nexus Backend

FastAPI backend for Nexus - Your Personal AI Life Operating System.

## Features

- **Skills Tracking**: Track skills with XP and level-up mechanics
- **Goals Management**: Create and track goals with progress logging
- **AI Chat**: Claude-powered conversational AI with context awareness
- **Memory System**: Vector-based semantic search with ChromaDB
- **WebSocket Streaming**: Real-time chat streaming

## Quick Start

### Prerequisites

- Python 3.11+
- ChromaDB (bundled)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration (at minimum, set ANTHROPIC_API_KEY)
```

### Database Setup

**SQLite (Default - Zero Setup!)**

SQLite is the default database - perfect for single-user personal dashboards. No additional setup required! The database file will be created automatically at `./data/nexus.db`.

```bash
# Run migrations
alembic upgrade head

# That's it! SQLite database is ready.
```

**PostgreSQL/Supabase (Optional)**

For production or multi-user deployments, you can use PostgreSQL:

1. Install PostgreSQL dependencies:
   ```bash
   pip install asyncpg supabase
   ```

2. Update your `.env` file:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
   DATABASE_URL_SYNC=postgresql://user:pass@host:5432/db
   ```

3. Run migrations:
   ```bash
   alembic upgrade head
   ```

### Running the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or run directly
python -m app.main
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI application entry
│   ├── api/              # API route handlers
│   │   ├── chat.py       # Chat + WebSocket endpoints
│   │   ├── skills.py     # Skills CRUD + XP logging
│   │   ├── goals.py      # Goals CRUD + progress
│   │   ├── widgets.py    # Widget data endpoints
│   │   └── memory.py     # Facts, patterns, search
│   ├── core/
│   │   ├── config.py     # Settings from environment
│   │   └── database.py   # Async SQLAlchemy setup
│   ├── ai/
│   │   ├── engine.py     # Claude integration
│   │   ├── context.py    # Context assembly
│   │   └── prompts.py    # System prompts
│   ├── memory/
│   │   ├── vector_store.py  # ChromaDB operations
│   │   └── obsidian.py   # Obsidian vault sync
│   ├── models/           # SQLAlchemy models
│   └── schemas/          # Pydantic schemas
├── alembic/              # Database migrations
├── data/                 # SQLite database + ChromaDB storage
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Chat
- `POST /api/chat` - Send message, get response
- `WS /api/chat/stream` - WebSocket for streaming
- `GET /api/chat/history` - Get conversation history

### Skills
- `GET /api/skills` - List all skills
- `POST /api/skills` - Create skill
- `GET /api/skills/{id}` - Get skill with history
- `POST /api/skills/{id}/log` - Log XP

### Goals
- `GET /api/goals` - List all goals
- `POST /api/goals` - Create goal
- `PATCH /api/goals/{id}` - Update goal
- `POST /api/goals/{id}/progress` - Log progress

### Memory
- `GET /api/memory/search` - Semantic search
- `GET /api/memory/facts` - List facts
- `POST /api/memory/facts` - Add fact
- `POST /api/memory/sync` - Sync from sources

### Widgets
- `GET /api/widgets/today` - Today's focus
- `GET /api/widgets/skills` - Skills summary
- `GET /api/widgets/goals` - Goals summary

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Yes | - |
| `DATABASE_URL` | Database connection URL (async) | No | `sqlite+aiosqlite:///./data/nexus.db` |
| `DATABASE_URL_SYNC` | Database connection URL (sync) | No | `sqlite:///./data/nexus.db` |
| `CHROMADB_PATH` | ChromaDB storage path | No | `./data/chroma` |
| `CORS_ORIGINS` | Allowed CORS origins | No | `["http://localhost:3000"]` |
| `DEBUG` | Enable debug mode | No | `true` |

### Optional PostgreSQL/Supabase Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
ruff check app/ --fix
```

### Creating Migrations

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Architecture

- **FastAPI**: Modern async Python web framework
- **SQLAlchemy 2.0**: Async ORM with SQLite (default) or PostgreSQL
- **SQLite**: Zero-config embedded database (default)
- **PostgreSQL**: Optional for production/multi-user (via Supabase or self-hosted)
- **ChromaDB**: Vector database for semantic search
- **Anthropic Claude**: AI conversation engine
- **Pydantic**: Data validation and settings
- **Alembic**: Database migrations

## License

MIT
