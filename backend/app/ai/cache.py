"""Caching layer for AI operations.

This module provides intelligent caching to reduce redundant API calls
and improve response times while minimizing costs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, TypeVar, Generic
from functools import wraps
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A cached value with metadata."""
    value: T
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > (self.created_at + self.ttl)

    @property
    def age(self) -> float:
        """Get the age of this entry in seconds."""
        return time.time() - self.created_at


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL support.

    Features:
    - Least Recently Used eviction
    - Time-to-live expiration
    - Hit/miss statistics
    - Memory-efficient with max size limit
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,  # 5 minutes
        name: str = "cache",
    ):
        """Initialize cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
            name: Cache name for logging
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.name = name
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[T]:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._hits += 1

        return entry.value

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional custom TTL
        """
        # Evict if at max size
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest

        self._cache[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl=ttl or self.default_ttl,
        )

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was found and removed
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern.

        Args:
            pattern: Pattern to match (simple prefix match)

        Returns:
            Number of keys invalidated
        """
        keys_to_remove = [k for k in self._cache if k.startswith(pattern)]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired:
            del self._cache[key]
        return len(expired)

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "name": self.name,
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
        }


# Global cache instances
_tool_cache: Optional[LRUCache] = None
_response_cache: Optional[LRUCache] = None
_embedding_cache: Optional[LRUCache] = None


def get_tool_cache() -> LRUCache:
    """Get the tool results cache."""
    global _tool_cache
    if _tool_cache is None:
        _tool_cache = LRUCache(
            max_size=500,
            default_ttl=300.0,  # 5 minutes for tool results
            name="tool_cache",
        )
    return _tool_cache


def get_response_cache() -> LRUCache:
    """Get the AI response cache."""
    global _response_cache
    if _response_cache is None:
        _response_cache = LRUCache(
            max_size=200,
            default_ttl=600.0,  # 10 minutes for responses
            name="response_cache",
        )
    return _response_cache


def get_embedding_cache() -> LRUCache:
    """Get the embedding cache."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = LRUCache(
            max_size=1000,
            default_ttl=3600.0,  # 1 hour for embeddings
            name="embedding_cache",
        )
    return _embedding_cache


# Cacheable tool configurations
# Tools that are safe to cache and their TTLs
CACHEABLE_TOOLS: Dict[str, float] = {
    # Read-only tools - safe to cache
    "list_skills": 60.0,          # 1 minute
    "list_goals": 60.0,
    "get_skill_details": 60.0,
    "get_goal_details": 60.0,
    "search_web_ddg": 300.0,      # 5 minutes
    "get_system_info": 30.0,      # 30 seconds
    "get_weather": 600.0,         # 10 minutes
    "get_stock_price": 60.0,      # 1 minute (market data)
    "get_stock_news": 300.0,      # 5 minutes
    "recall_facts": 120.0,        # 2 minutes
    "list_files": 30.0,           # 30 seconds
    "read_file": 60.0,            # 1 minute

    # MCP tools that are read-only
    "mcp_filesystem_read_file": 60.0,
    "mcp_filesystem_list_directory": 30.0,
    "mcp_github_list_repos": 120.0,
    "mcp_github_get_repo": 120.0,
    "mcp_brave_search": 300.0,
    "mcp_memory_recall": 120.0,
}

# Tools that should NEVER be cached (state-changing)
NON_CACHEABLE_TOOLS = {
    "create_skill", "add_skill_xp", "delete_skill",
    "create_goal", "update_goal_progress", "complete_goal", "delete_goal",
    "remember_fact", "forget_fact",
    "write_file", "execute_code", "run_shell_command",
    "send_email", "create_calendar_event",
    "buy_stock", "sell_stock",
    "mcp_filesystem_write_file", "mcp_filesystem_delete_file",
    "mcp_github_create_issue", "mcp_github_create_pr",
    "mcp_memory_store",
}


def cached_tool(ttl: Optional[float] = None):
    """Decorator to cache tool execution results.

    Usage:
        @cached_tool(ttl=60)
        async def my_tool(arg1, arg2):
            ...

    Args:
        ttl: Custom TTL in seconds (uses tool-specific default if not provided)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_tool_cache()
            tool_name = func.__name__

            # Check if this tool is cacheable
            if tool_name in NON_CACHEABLE_TOOLS:
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = f"{tool_name}:{cache._generate_key(*args, **kwargs)}"

            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {tool_name}")
                return cached_result

            # Execute and cache
            result = await func(*args, **kwargs)

            # Determine TTL
            effective_ttl = ttl or CACHEABLE_TOOLS.get(tool_name, 60.0)
            cache.set(cache_key, result, ttl=effective_ttl)

            logger.debug(f"Cached {tool_name} result (TTL: {effective_ttl}s)")
            return result

        return wrapper
    return decorator


def get_all_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches."""
    return {
        "tool_cache": get_tool_cache().stats,
        "response_cache": get_response_cache().stats,
        "embedding_cache": get_embedding_cache().stats,
    }


def clear_all_caches() -> None:
    """Clear all caches."""
    get_tool_cache().clear()
    get_response_cache().clear()
    get_embedding_cache().clear()
    logger.info("All caches cleared")
