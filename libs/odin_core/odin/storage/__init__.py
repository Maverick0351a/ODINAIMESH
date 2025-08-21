"""
ODIN Storage Backends

Storage abstraction layer supporting multiple backends:
- In-memory storage for development/testing
- Firestore for production cloud deployment
- Future: PostgreSQL, MongoDB, etc.
"""

import os
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


# Storage factory function
def create_storage_from_env() -> StorageBackend:
    """Create storage backend from environment configuration."""
    storage_type = os.getenv("ODIN_STORAGE_TYPE", "memory")
    
    if storage_type == "firestore":
        try:
            from .firestore import FirestoreStorage
            return FirestoreStorage()
        except ImportError:
            # Fallback to memory storage if Firestore dependencies not available
            from .memory import InMemoryStorage
            return InMemoryStorage()
    else:
        # Default to in-memory storage
        from .memory import InMemoryStorage
        return InMemoryStorage()


# Storage key utilities
def key_oml(trace_id: str) -> str:
    """Generate OML storage key."""
    return f"oml:{trace_id}"


def key_receipt(trace_id: str, hop_id: str) -> str:
    """Generate receipt storage key."""
    return f"receipt:{trace_id}:{hop_id}"


def key_transform_receipt(transformation_id: str) -> str:
    """Generate transformation receipt storage key."""
    return f"transform_receipt:{transformation_id}"


def cache_transform_receipt_set(transformation_id: str, receipt_data: Dict[str, Any]) -> None:
    """Cache transformation receipt (in-memory for demo)."""
    # In production, this would use Redis or another cache
    if not hasattr(cache_transform_receipt_set, '_cache'):
        cache_transform_receipt_set._cache = {}
    
    cache_transform_receipt_set._cache[transformation_id] = receipt_data


def cache_transform_receipt_get(transformation_id: str) -> Optional[Dict[str, Any]]:
    """Get cached transformation receipt."""
    if not hasattr(cache_transform_receipt_set, '_cache'):
        return None
    
    return cache_transform_receipt_set._cache.get(transformation_id)


def receipt_metadata_from_env() -> Dict[str, Any]:
    """Generate receipt metadata from environment."""
    return {
        "storage_backend": os.getenv("ODIN_STORAGE_TYPE", "memory"),
        "timestamp": "2025-08-20T21:00:00Z",
        "version": "1.0.0"
    }


# HTTP headers for storage URLs
HDR_OML_C_URL = "x-odin-oml-c-url"
HDR_RECEIPT_URL = "x-odin-receipt-url"
