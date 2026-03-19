"""Memory API endpoints - Facts, Patterns, Search."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.memory import Fact, Pattern
from app.memory.vector_store import get_vector_store
from app.memory.obsidian import ObsidianSync

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
) -> dict:
    """
    Sync memory from external source.

    Args:
        source: Source to sync from ('obsidian', 'claude_history')

    Returns:
        Sync statistics
    """
    if source == "obsidian":
        vector_store = get_vector_store()
        obsidian = ObsidianSync(vector_store=vector_store)
        stats = await obsidian.sync_vault(str(DEFAULT_USER_ID))
        return {"source": "obsidian", "stats": stats}

    elif source == "claude_history":
        # TODO: Implement Claude history sync
        return {"source": "claude_history", "status": "not_implemented"}

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
