# Nexus

Your Personal AI Life Operating System.

Nexus is an intelligent personal dashboard that combines AI conversation, skill tracking, goal management, and memory systems to help you organize and optimize your life.

## Features

- **AI-Powered Chat**: Conversational AI with Claude that understands your context
- **Skills Tracking**: Track skills with XP and level-up mechanics
- **Goals Management**: Create and monitor goals with progress logging
- **Memory System**: Semantic search across your notes, conversations, and data
- **Widget Dashboard**: Customizable widgets for daily focus, skills, and goals
- **Obsidian Integration**: Sync with your Obsidian vault for enhanced context

## Architecture

```
nexus/
├── frontend/          # Next.js 15 + React + TailwindCSS
├── backend/           # FastAPI + SQLAlchemy + ChromaDB
├── docs/              # Design documentation
└── docker-compose.yml # Local development services
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 15, React, TailwindCSS, shadcn/ui |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic |
| Database | Supabase (PostgreSQL) |
| Vector Store | ChromaDB |
| Cache | Redis |
| AI | Anthropic Claude |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Supabase account (free tier)
- Anthropic API key

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd nexus

# Create data directory for ChromaDB persistence
mkdir -p data/chroma
```

### 2. Environment Configuration

**Backend** (`backend/.env`):
```bash
cd backend
cp .env.example .env
# Edit .env with your credentials:
# - ANTHROPIC_API_KEY
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - DATABASE_URL
# - DATABASE_URL_SYNC
```

**Frontend** (`frontend/.env.local`):
```bash
cd frontend
cp .env.local.example .env.local
# Edit if needed (defaults to localhost:8000)
```

### 3. Start Development Environment

**Option A: Use the start script (recommended)**

```bash
chmod +x start.sh
./start.sh
```

**Option B: Manual startup**

```bash
# Start Docker services (ChromaDB, Redis)
docker-compose up -d

# Start backend (new terminal)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

### 4. Access the Application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| ChromaDB | http://localhost:8001 |

## Docker Services

The `docker-compose.yml` provides:

- **ChromaDB** (port 8001): Vector database for semantic memory search
- **Redis** (port 6379): Caching and session storage

### Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Reset ChromaDB data
docker-compose down -v
rm -rf data/chroma/*
docker-compose up -d
```

### Development Overrides

For additional debugging tools:

```bash
# Start with Redis Insight GUI
docker-compose -f docker-compose.yml -f docker-compose.dev.yml --profile debug up -d
# Access Redis Insight at http://localhost:8002
```

## Database Setup (Supabase)

1. Create a project at [supabase.com](https://supabase.com)
2. Get connection credentials from Settings > Database
3. Run migrations:

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

## Project Documentation

- [Backend README](./backend/README.md) - API endpoints, setup, architecture
- [Frontend README](./frontend/README.md) - Next.js setup and development
- [Design Docs](./docs/design/) - System architecture and design decisions

## Development

### Backend

```bash
cd backend
source venv/bin/activate

# Run server
uvicorn app.main:app --reload

# Run tests
pytest

# Format code
black app/
ruff check app/ --fix
```

### Frontend

```bash
cd frontend

# Run dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Yes |
| `DATABASE_URL` | PostgreSQL async URL | Yes |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL | Yes |
| `REDIS_URL` | Redis connection URL | No |
| `CHROMADB_PATH` | ChromaDB storage path | No |

### Frontend (`frontend/.env.local`)

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | No (default: http://localhost:8000) |

## License

MIT
