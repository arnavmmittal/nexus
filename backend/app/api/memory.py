"""Memory API endpoints - Facts, Patterns, Search, Obsidian, and Claude Sync."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.memory import Conversation, Fact, Pattern
from app.memory.vector_store import get_vector_store
from app.memory.obsidian import get_obsidian_sync
from app.memory.claude_sync import ClaudeSync, get_claude_sync

router = APIRouter()

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


# Schemas
class FactCreate(BaseModel):
    """Schema for creating a fact."""

    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str | None = None


class FactResponse(BaseModel):
    """Schema for fact response."""

    id: UUID
    user_id: UUID
    category: str
    key: str
    value: str
    confidence: float
    source: str | None
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class PatternResponse(BaseModel):
    """Schema for pattern response."""

    id: UUID
    user_id: UUID
    domain: str
    pattern_type: str
    description: str
    evidence: dict
    confidence: float
    discovered_at: Any

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """Schema for search request."""

    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    """Schema for search result."""

    id: str
    content: str
    score: float
    metadata: dict


# Claude Sync Schemas
class ClaudeImportRequest(BaseModel):
    """Schema for Claude import request."""

    directory: str | None = Field(
        default=None,
        description="Directory to import from (defaults to CLAUDE_HISTORY_PATH)",
    )
    force: bool = Field(
        default=False,
        description="Force re-import of existing sessions",
    )


class ClaudeSessionInfo(BaseModel):
    """Schema for Claude session info."""

    session_id: str
    project_path: str
    file_path: str
    size_bytes: int
    modified_at: str


class ClaudeConversationResponse(BaseModel):
    """Schema for Claude conversation response."""

    id: UUID
    source: str
    started_at: Any
    ended_at: Any
    summary: str | None
    extracted_facts: dict | None
    extracted_skills: dict | None

    model_config = {"from_attributes": True}


# Endpoints
@router.get("/search")
async def search_memory(
    query: str,
    limit: int = 10,
) -> list[SearchResult]:
    """
    Search memory using semantic search.

    Args:
        query: Search query
        limit: Maximum results

    Returns:
        List of relevant memories
    """
    vector_store = get_vector_store()

    results = await vector_store.search(
        query=query,
        user_id=str(DEFAULT_USER_ID),
        limit=limit,
    )

    return [SearchResult(**r) for r in results]


@router.get("/facts", response_model=list[FactResponse])
async def list_facts(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all facts for the current user.

    Args:
        db: Database session
        category: Optional filter by category
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of facts
    """
    query = select(Fact).where(Fact.user_id == DEFAULT_USER_ID)

    if category:
        query = query.where(Fact.category == category)

    query = query.order_by(Fact.updated_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/facts", response_model=FactResponse, status_code=status.HTTP_201_CREATED)
async def create_fact(
    fact_data: FactCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new fact.

    Args:
        fact_data: Fact data
        db: Database session

    Returns:
        Created fact
    """
    # Check for existing fact with same key
    existing = await db.execute(
        select(Fact).where(
            Fact.user_id == DEFAULT_USER_ID,
            Fact.category == fact_data.category,
            Fact.key == fact_data.key,
        )
    )
    existing_fact = existing.scalar_one_or_none()

    if existing_fact:
        # Update existing fact
        existing_fact.value = fact_data.value
        existing_fact.confidence = fact_data.confidence
        if fact_data.source:
            existing_fact.source = fact_data.source
        await db.flush()
        return existing_fact

    # Create new fact
    fact = Fact(
        user_id=DEFAULT_USER_ID,
        category=fact_data.category,
        key=fact_data.key,
        value=fact_data.value,
        confidence=fact_data.confidence,
        source=fact_data.source,
    )
    db.add(fact)
    await db.flush()

    # Also add to vector store
    vector_store = get_vector_store()
    await vector_store.add_document(
        content=f"{fact_data.key}: {fact_data.value}",
        user_id=str(DEFAULT_USER_ID),
        metadata={
            "type": "fact",
            "category": fact_data.category,
            "fact_id": str(fact.id),
        },
    )

    return fact


@router.get("/facts/{fact_id}", response_model=FactResponse)
async def get_fact(
    fact_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific fact."""
    result = await db.execute(
        select(Fact).where(Fact.id == fact_id, Fact.user_id == DEFAULT_USER_ID)
    )
    fact = result.scalar_one_or_none()

    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact not found",
        )

    return fact


@router.delete("/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(
    fact_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a fact."""
    result = await db.execute(
        select(Fact).where(Fact.id == fact_id, Fact.user_id == DEFAULT_USER_ID)
    )
    fact = result.scalar_one_or_none()

    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact not found",
        )

    await db.delete(fact)


@router.get("/patterns", response_model=list[PatternResponse])
async def list_patterns(
    db: Annotated[AsyncSession, Depends(get_db)],
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all patterns for the current user.

    Args:
        db: Database session
        domain: Optional filter by domain
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of patterns
    """
    query = select(Pattern).where(Pattern.user_id == DEFAULT_USER_ID)

    if domain:
        query = query.where(Pattern.domain == domain)

    query = query.order_by(Pattern.confidence.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/sync")
async def sync_memory(
    source: str = "obsidian",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Sync memory from external source.

    Args:
        source: Source to sync from ('obsidian', 'claude_history')
        db: Database session

    Returns:
        Sync statistics
    """
    if source == "obsidian":
        vector_store = get_vector_store()
        obsidian = ObsidianSync(vector_store=vector_store)
        stats = await obsidian.sync_vault(str(DEFAULT_USER_ID))
        return {"source": "obsidian", "stats": stats}

    elif source == "claude_history":
        vector_store = get_vector_store()
        claude_sync = get_claude_sync(vector_store=vector_store)
        stats = await claude_sync.sync_directory(
            directory=None,
            user_id=DEFAULT_USER_ID,
            db=db,
        )
        return {"source": "claude_history", "stats": stats}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown source: {source}",
    )


@router.get("/stats")
async def get_memory_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get memory statistics."""
    # Count facts
    facts_result = await db.execute(
        select(Fact).where(Fact.user_id == DEFAULT_USER_ID)
    )
    facts_count = len(facts_result.scalars().all())

    # Count patterns
    patterns_result = await db.execute(
        select(Pattern).where(Pattern.user_id == DEFAULT_USER_ID)
    )
    patterns_count = len(patterns_result.scalars().all())

    # Get vector store stats
    vector_store = get_vector_store()
    vector_stats = vector_store.get_stats()

    return {
        "facts_count": facts_count,
        "patterns_count": patterns_count,
        "vector_store": vector_stats,
    }


# =============================================================================
# Claude Code Integration Endpoints
# =============================================================================


@router.post("/claude/import")
async def import_claude_conversations(
    request: ClaudeImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Import Claude Code conversations from a directory.

    Parses JSONL conversation files and:
    - Stores conversation metadata in PostgreSQL
    - Indexes content in ChromaDB for semantic search
    - Extracts and awards XP to detected skills

    Args:
        request: Import configuration
        db: Database session

    Returns:
        Import statistics including sessions imported and skills updated
    """
    vector_store = get_vector_store()
    claude_sync = get_claude_sync(vector_store=vector_store)

    stats = await claude_sync.sync_directory(
        directory=request.directory,
        user_id=DEFAULT_USER_ID,
        db=db,
        force=request.force,
    )

    if "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=stats["error"],
        )

    return {
        "status": "success",
        "imported": stats.get("imported", 0),
        "skipped": stats.get("skipped", 0),
        "errors": stats.get("errors", 0),
        "skills_updated": stats.get("skills_updated", 0),
        "sessions": stats.get("sessions", []),
    }


@router.get("/claude/sessions", response_model=list[ClaudeSessionInfo])
async def list_claude_sessions(
    project: str | None = None,
    limit: int = 50,
) -> list[ClaudeSessionInfo]:
    """
    List available Claude Code sessions.

    Returns sessions from the Claude history directory that can be imported.

    Args:
        project: Optional filter by project path substring
        limit: Maximum results

    Returns:
        List of available sessions with metadata
    """
    claude_sync = get_claude_sync()
    sessions = claude_sync.list_sessions(project_path=project)

    return [ClaudeSessionInfo(**s) for s in sessions[:limit]]


@router.get("/claude/search")
async def search_claude_conversations(
    query: str,
    limit: int = 10,
) -> list[SearchResult]:
    """
    Search across imported Claude Code conversations.

    Uses semantic search to find relevant conversation content.

    Args:
        query: Search query
        limit: Maximum results

    Returns:
        List of matching conversation snippets
    """
    vector_store = get_vector_store()
    claude_sync = get_claude_sync(vector_store=vector_store)

    results = await claude_sync.search_conversations(
        query=query,
        user_id=str(DEFAULT_USER_ID),
        limit=limit,
    )

    return [SearchResult(**r) for r in results]


@router.get("/claude/conversations", response_model=list[ClaudeConversationResponse])
async def list_claude_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[ClaudeConversationResponse]:
    """
    List imported Claude Code conversations.

    Args:
        db: Database session
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of imported conversations
    """
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == DEFAULT_USER_ID,
            Conversation.source == "claude_code",
        )
        .order_by(Conversation.started_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )

    return result.scalars().all()


@router.get("/claude/conversations/{conversation_id}", response_model=ClaudeConversationResponse)
async def get_claude_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClaudeConversationResponse:
    """
    Get details of a specific Claude conversation.

    Args:
        conversation_id: Conversation ID
        db: Database session

    Returns:
        Conversation details
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == DEFAULT_USER_ID,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.get("/claude/projects")
async def list_claude_projects() -> list[dict]:
    """
    Discover Claude Code projects.

    Returns available projects with session counts.

    Returns:
        List of project info
    """
    claude_sync = get_claude_sync()
    return claude_sync.discover_projects()


@router.post("/claude/parse-session")
async def parse_claude_session(
    session_path: str,
) -> dict:
    """
    Parse a single Claude session file without importing.

    Useful for previewing what will be extracted from a session.

    Args:
        session_path: Path to JSONL file

    Returns:
        Parsed session data
    """
    from pathlib import Path

    file_path = Path(session_path).expanduser()
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session file not found: {session_path}",
        )

    claude_sync = get_claude_sync()
    session = claude_sync.parse_jsonl_file(file_path)

    return {
        "session_id": session.session_id,
        "project_path": session.project_path,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_minutes": session.duration_minutes,
        "message_count": session.message_count,
        "code_blocks": session.total_code_blocks,
        "detected_skills": session.detected_skills,
        "detected_decisions": session.detected_decisions,
        "git_branch": session.git_branch,
        "version": session.version,
        "messages": [
            {
                "role": m.role,
                "content": m.content[:500] + "..." if len(m.content) > 500 else m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "code_blocks": [
                    {"language": b.language, "lines": b.line_count}
                    for b in m.code_blocks
                ],
            }
            for m in session.messages[:20]  # Limit preview to 20 messages
        ],
    }
