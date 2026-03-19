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
- PostgreSQL 15+
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
# Edit .env with your configuration
```

### Database Setup

```bash
# Start PostgreSQL (via Docker or local install)
docker run -d --name nexus-db \
  -e POSTGRES_USER=nexus \
  -e POSTGRES_PASSWORD=nexus \
  -e POSTGRES_DB=nexus \
  -p 5432:5432 \
  postgres:15

# Run migrations
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

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `DATABASE_URL` | PostgreSQL async URL | `postgresql+asyncpg://...` |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL | `postgresql://...` |
| `CHROMADB_PATH` | ChromaDB storage path | `./data/chroma` |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |
| `DEBUG` | Enable debug mode | `true` |

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
- **SQLAlchemy 2.0**: Async ORM with PostgreSQL
- **ChromaDB**: Vector database for semantic search
- **Anthropic Claude**: AI conversation engine
- **Pydantic**: Data validation and settings
- **Alembic**: Database migrations

## License

MIT
