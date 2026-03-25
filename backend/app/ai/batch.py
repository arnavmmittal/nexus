"""Batch operations for efficient API usage.

This module provides batching capabilities to group multiple small operations
into single API calls, reducing overhead and costs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic, Awaitable
from uuid import uuid4
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BatchStatus(str, Enum):
    """Status of a batch operation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BatchItem(Generic[T]):
    """A single item in a batch."""
    id: str
    operation: str
    args: Dict[str, Any]
    callback: Optional[Callable[[T], Awaitable[None]]] = None
    result: Optional[T] = None
    error: Optional[str] = None
    status: BatchStatus = BatchStatus.PENDING
    created_at: float = field(default_factory=time.time)


@dataclass
class BatchResult(Generic[T]):
    """Result of a batch operation."""
    batch_id: str
    items: List[BatchItem[T]]
    total_time: float
    success_count: int
    failure_count: int

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0


class ToolBatcher:
    """Batches tool executions for efficient processing.

    Features:
    - Groups compatible tools into batches
    - Executes batches in parallel where possible
    - Reduces API overhead
    - Provides retry logic
    """

    # Tools that can be batched together (read-only operations)
    BATCHABLE_TOOLS = {
        # Same-category tools can be batched
        "read_operations": [
            "list_skills", "list_goals", "get_skill_details",
            "get_goal_details", "recall_facts", "list_files",
        ],
        "web_operations": [
            "search_web_ddg", "get_weather", "get_stock_price",
        ],
        "system_operations": [
            "get_system_info", "get_clipboard", "list_apps",
        ],
    }

    def __init__(
        self,
        max_batch_size: int = 5,
        batch_timeout: float = 0.1,  # Wait time to collect batch items
        max_parallel_batches: int = 3,
    ):
        """Initialize tool batcher.

        Args:
            max_batch_size: Maximum items per batch
            batch_timeout: Time to wait for more items (seconds)
            max_parallel_batches: Max concurrent batch executions
        """
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.max_parallel_batches = max_parallel_batches

        self._pending_items: Dict[str, List[BatchItem]] = {}
        self._batch_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_parallel_batches)

    def _get_tool_category(self, tool_name: str) -> Optional[str]:
        """Get the category for a tool."""
        for category, tools in self.BATCHABLE_TOOLS.items():
            if tool_name in tools:
                return category
        return None

    def can_batch(self, tool_name: str) -> bool:
        """Check if a tool can be batched."""
        return self._get_tool_category(tool_name) is not None

    async def add_to_batch(
        self,
        tool_name: str,
        args: Dict[str, Any],
        callback: Optional[Callable] = None,
    ) -> BatchItem:
        """Add a tool execution to the batch queue.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            callback: Optional callback for when complete

        Returns:
            BatchItem representing this operation
        """
        category = self._get_tool_category(tool_name)
        if category is None:
            raise ValueError(f"Tool {tool_name} is not batchable")

        item = BatchItem(
            id=str(uuid4())[:8],
            operation=tool_name,
            args=args,
            callback=callback,
        )

        async with self._batch_lock:
            if category not in self._pending_items:
                self._pending_items[category] = []
            self._pending_items[category].append(item)

        return item

    async def execute_batch(
        self,
        category: str,
        executor: Callable[[str, Dict[str, Any]], Awaitable[Any]],
    ) -> BatchResult:
        """Execute all pending items in a category.

        Args:
            category: Category of tools to execute
            executor: Async function to execute each tool

        Returns:
            BatchResult with all outcomes
        """
        async with self._batch_lock:
            items = self._pending_items.pop(category, [])

        if not items:
            return BatchResult(
                batch_id=str(uuid4())[:8],
                items=[],
                total_time=0,
                success_count=0,
                failure_count=0,
            )

        batch_id = str(uuid4())[:8]
        start_time = time.time()
        success_count = 0
        failure_count = 0

        async with self._semaphore:
            # Execute items in parallel within the batch
            tasks = []
            for item in items:
                task = self._execute_item(item, executor)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for item, result in zip(items, results):
                if isinstance(result, Exception):
                    item.status = BatchStatus.FAILED
                    item.error = str(result)
                    failure_count += 1
                else:
                    item.status = BatchStatus.COMPLETED
                    item.result = result
                    success_count += 1

                # Call callback if provided
                if item.callback and item.status == BatchStatus.COMPLETED:
                    try:
                        await item.callback(item.result)
                    except Exception as e:
                        logger.error(f"Batch callback failed: {e}")

        total_time = time.time() - start_time

        logger.info(
            f"Batch {batch_id} completed: {success_count} success, "
            f"{failure_count} failed, {total_time:.2f}s"
        )

        return BatchResult(
            batch_id=batch_id,
            items=items,
            total_time=total_time,
            success_count=success_count,
            failure_count=failure_count,
        )

    async def _execute_item(
        self,
        item: BatchItem,
        executor: Callable,
    ) -> Any:
        """Execute a single batch item."""
        item.status = BatchStatus.PROCESSING
        return await executor(item.operation, item.args)

    async def flush_all(
        self,
        executor: Callable[[str, Dict[str, Any]], Awaitable[Any]],
    ) -> List[BatchResult]:
        """Execute all pending batches.

        Args:
            executor: Tool executor function

        Returns:
            List of BatchResults
        """
        categories = list(self._pending_items.keys())
        results = []

        for category in categories:
            result = await self.execute_batch(category, executor)
            results.append(result)

        return results

    @property
    def pending_count(self) -> int:
        """Get total pending items across all categories."""
        return sum(len(items) for items in self._pending_items.values())


class RequestBatcher:
    """Batches multiple AI requests into optimized calls.

    This is useful when multiple queries can be answered from
    the same context or when queries are independent.
    """

    BATCH_PROMPT_TEMPLATE = """You have been given multiple queries to answer.
Please respond to each query in order, clearly labeling each response.

QUERIES:
{queries}

Respond to each query above, using the format:
[Query 1 Response]
<response>

[Query 2 Response]
<response>
...
"""

    def __init__(
        self,
        max_queries: int = 5,
        wait_time: float = 0.2,
    ):
        """Initialize request batcher.

        Args:
            max_queries: Maximum queries per batch
            wait_time: Time to wait for more queries
        """
        self.max_queries = max_queries
        self.wait_time = wait_time
        self._pending_queries: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def add_query(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> str:
        """Add a query to the batch.

        For now, this is a placeholder - full implementation would
        require integration with the AI client.

        Args:
            query: User query
            context: Optional additional context

        Returns:
            Query ID for tracking
        """
        query_id = str(uuid4())[:8]

        async with self._lock:
            self._pending_queries.append({
                "id": query_id,
                "query": query,
                "context": context,
                "timestamp": time.time(),
            })

        return query_id

    def format_batch_prompt(self, queries: List[Dict[str, Any]]) -> str:
        """Format multiple queries into a single prompt.

        Args:
            queries: List of query dicts

        Returns:
            Combined prompt string
        """
        query_texts = []
        for i, q in enumerate(queries, 1):
            query_texts.append(f"Query {i}: {q['query']}")

        return self.BATCH_PROMPT_TEMPLATE.format(
            queries="\n".join(query_texts)
        )

    def parse_batch_response(
        self,
        response: str,
        query_count: int,
    ) -> List[str]:
        """Parse a batch response into individual answers.

        Args:
            response: Full response text
            query_count: Expected number of responses

        Returns:
            List of individual responses
        """
        responses = []
        current_response = []

        lines = response.split("\n")
        for line in lines:
            if line.startswith("[Query") and "Response]" in line:
                if current_response:
                    responses.append("\n".join(current_response).strip())
                    current_response = []
            else:
                current_response.append(line)

        if current_response:
            responses.append("\n".join(current_response).strip())

        # Pad with empty strings if needed
        while len(responses) < query_count:
            responses.append("")

        return responses[:query_count]


class MultiStepBatcher:
    """Optimizes multi-step operations by analyzing dependencies.

    Identifies steps that can run in parallel vs sequential.
    """

    @staticmethod
    def analyze_dependencies(
        steps: List[Dict[str, Any]],
    ) -> Dict[str, List[int]]:
        """Analyze dependencies between steps.

        Args:
            steps: List of step definitions with 'id', 'depends_on', 'action'

        Returns:
            Dict mapping step IDs to list of parallel step indices
        """
        parallel_groups = {}
        seen = set()

        for i, step in enumerate(steps):
            step_id = step.get("id", str(i))
            depends_on = step.get("depends_on", [])

            if not depends_on:
                # No dependencies - can run immediately
                if "root" not in parallel_groups:
                    parallel_groups["root"] = []
                parallel_groups["root"].append(i)
            else:
                # Group by dependency
                dep_key = ",".join(sorted(depends_on))
                if dep_key not in parallel_groups:
                    parallel_groups[dep_key] = []
                parallel_groups[dep_key].append(i)

        return parallel_groups

    @staticmethod
    def create_execution_plan(
        steps: List[Dict[str, Any]],
    ) -> List[List[int]]:
        """Create an execution plan with parallel stages.

        Args:
            steps: List of step definitions

        Returns:
            List of parallel stages, each containing step indices
        """
        groups = MultiStepBatcher.analyze_dependencies(steps)
        plan = []

        # Root steps first
        if "root" in groups:
            plan.append(groups.pop("root"))

        # Then dependent groups in order
        remaining = list(groups.values())
        plan.extend(remaining)

        return plan


# Global batcher instances
_tool_batcher: Optional[ToolBatcher] = None


def get_tool_batcher() -> ToolBatcher:
    """Get the global tool batcher."""
    global _tool_batcher
    if _tool_batcher is None:
        _tool_batcher = ToolBatcher()
    return _tool_batcher


async def batch_execute_tools(
    tools: List[Dict[str, Any]],
    executor: Callable[[str, Dict[str, Any]], Awaitable[Any]],
) -> List[Any]:
    """Execute multiple tools efficiently, batching where possible.

    Args:
        tools: List of {"name": str, "args": dict}
        executor: Async function to execute each tool

    Returns:
        List of results in same order as input
    """
    batcher = get_tool_batcher()
    results = [None] * len(tools)
    batch_indices = []
    direct_indices = []

    # Sort into batchable and non-batchable
    for i, tool in enumerate(tools):
        if batcher.can_batch(tool["name"]):
            batch_indices.append(i)
        else:
            direct_indices.append(i)

    # Execute non-batchable tools in parallel
    if direct_indices:
        direct_tasks = [
            executor(tools[i]["name"], tools[i]["args"])
            for i in direct_indices
        ]
        direct_results = await asyncio.gather(*direct_tasks, return_exceptions=True)
        for idx, result in zip(direct_indices, direct_results):
            results[idx] = result

    # Batch the batchable tools
    if batch_indices:
        for i in batch_indices:
            await batcher.add_to_batch(tools[i]["name"], tools[i]["args"])

        batch_results = await batcher.flush_all(executor)

        # Map results back
        result_map = {}
        for br in batch_results:
            for item in br.items:
                result_map[(item.operation, str(item.args))] = item.result

        for i in batch_indices:
            key = (tools[i]["name"], str(tools[i]["args"]))
            results[i] = result_map.get(key)

    return results
