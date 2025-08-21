"""
In-Memory Storage Backend

Simple in-memory storage backend for development and testing.
"""

from typing import Dict, List, Optional, Any
import asyncio
from collections import defaultdict

class InMemoryStorage:
    """In-memory storage backend for development/testing."""
    
    def __init__(self):
        self._data = defaultdict(dict)
        self._lock = asyncio.Lock()
    
    async def get(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        async with self._lock:
            return self._data[collection].get(document_id)
    
    async def set(self, collection: str, document_id: str, data: Dict[str, Any]) -> None:
        """Set a document."""
        async with self._lock:
            self._data[collection][document_id] = data.copy()
    
    async def delete(self, collection: str, document_id: str) -> None:
        """Delete a document."""
        async with self._lock:
            self._data[collection].pop(document_id, None)
    
    async def list(self, collection: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List documents in a collection."""
        async with self._lock:
            items = list(self._data[collection].values())
            return items[:limit]
    
    async def clear(self) -> None:
        """Clear all data (for testing)."""
        async with self._lock:
            self._data.clear()
