"""
ODIN Storage Backends

Storage abstraction layer supporting multiple backends:
- In-memory storage for development/testing
- Firestore for production cloud deployment
- Future: PostgreSQL, MongoDB, etc.
"""

from typing import Protocol, Any, Dict, List, Optional
import abc

class StorageBackend(Protocol):
    """Storage backend interface."""
    
    async def get(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        ...
    
    async def set(self, collection: str, document_id: str, data: Dict[str, Any]) -> None:
        """Set a document."""
        ...
    
    async def delete(self, collection: str, document_id: str) -> None:
        """Delete a document."""
        ...
    
    async def list(self, collection: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List documents in a collection."""
        ...
