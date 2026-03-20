"""ChromaDB vector store for semantic search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Vector store using ChromaDB for semantic search.

    Stores embeddings of:
    - Conversation snippets
    - Facts and patterns
    - Obsidian notes
    """

    COLLECTION_NAME = "nexus_memories"

    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory for persistent storage
        """
        persist_dir = persist_directory or str(settings.chromadb_path_resolved)

        # Ensure directory exists
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"Initialized vector store at {persist_dir}")

    async def add_document(
        self,
        content: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
        document_id: Optional[str] = None,
    ) -> str:
        """
        Add a document to the vector store.

        Args:
            content: Document content
            user_id: User ID for filtering
            metadata: Additional metadata
            document_id: Optional document ID

        Returns:
            Document ID
        """
        import uuid

        doc_id = document_id or str(uuid.uuid4())

        # Build metadata
        doc_metadata = {
            "user_id": user_id,
            **(metadata or {}),
        }

        # Add to collection (ChromaDB handles embedding)
        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[doc_metadata],
        )

        logger.debug(f"Added document {doc_id} to vector store")
        return doc_id

    async def add_documents(
        self,
        contents: List[str],
        user_id: str,
        metadatas: List[dict[str, Any]] | None = None,
        document_ids: List[str] | None = None,
    ) -> List[str]:
        """
        Add multiple documents to the vector store.

        Args:
            contents: List of document contents
            user_id: User ID for filtering
            metadatas: List of metadata dicts
            document_ids: Optional list of document IDs

        Returns:
            List of document IDs
        """
        import uuid

        doc_ids = document_ids or [str(uuid.uuid4()) for _ in contents]

        # Build metadata for all documents
        doc_metadatas = []
        for i, content in enumerate(contents):
            meta = {"user_id": user_id}
            if metadatas and i < len(metadatas):
                meta.update(metadatas[i])
            doc_metadatas.append(meta)

        # Add to collection
        self.collection.add(
            ids=doc_ids,
            documents=contents,
            metadatas=doc_metadatas,
        )

        logger.debug(f"Added {len(doc_ids)} documents to vector store")
        return doc_ids

    async def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[dict[str, Any]]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            user_id: User ID for filtering
            limit: Maximum results
            min_score: Minimum relevance score (0-1)

        Returns:
            List of matching documents with metadata
        """
        # Query collection with user filter
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        documents = []
        for i in range(len(results["ids"][0])):
            # Convert distance to similarity score (cosine distance)
            distance = results["distances"][0][i]
            score = 1 - distance  # Convert to similarity

            if score >= min_score:
                documents.append(
                    {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": score,
                    }
                )

        return documents

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the vector store.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted
        """
        try:
            self.collection.delete(ids=[document_id])
            logger.debug(f"Deleted document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    async def delete_user_documents(self, user_id: str) -> int:
        """
        Delete all documents for a user.

        Args:
            user_id: User ID

        Returns:
            Number of deleted documents
        """
        # Get all document IDs for user
        results = self.collection.get(
            where={"user_id": user_id},
            include=[],
        )

        if not results["ids"]:
            return 0

        # Delete documents
        self.collection.delete(ids=results["ids"])
        logger.info(f"Deleted {len(results['ids'])} documents for user {user_id}")
        return len(results["ids"])

    def get_stats(self) -> dict[str, Any]:
        """Get vector store statistics."""
        return {
            "collection_name": self.COLLECTION_NAME,
            "document_count": self.collection.count(),
        }


# Global instance (lazy initialization)
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
