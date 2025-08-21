"""
VAI (Verifiable Agent Identity) Registry

Manages agent registration, validation, and approval workflow for 0.9.0-beta.
Provides Firestore-backed agent identity management with HEL policy integration.
"""
from __future__ import annotations

import os
import time
import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

try:
    from google.cloud import firestore  # type: ignore
    from google.api_core import exceptions as gcp_exceptions  # type: ignore
except ImportError:
    firestore = None  # type: ignore
    gcp_exceptions = None  # type: ignore


@dataclass
class AgentInfo:
    """Agent identity record for VAI system."""
    agent_id: str
    public_key: str  # Base64-encoded Ed25519 public key
    metadata: Dict[str, Any]
    status: str = "pending"  # pending, approved, rejected, suspended
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    approved_by: Optional[str] = None
    approval_ts: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent_id": self.agent_id,
            "public_key": self.public_key,
            "metadata": self.metadata,
            "status": self.status,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
            "approved_by": self.approved_by,
            "approval_ts": self.approval_ts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """Create from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            public_key=data["public_key"],
            metadata=data.get("metadata", {}),
            status=data.get("status", "pending"),
            created_ts=data.get("created_ts"),
            updated_ts=data.get("updated_ts"),
            approved_by=data.get("approved_by"),
            approval_ts=data.get("approval_ts"),
        )


class AgentRegistry:
    """
    VAI Agent Registry with Firestore backend.
    
    Manages agent lifecycle:
    1. Registration (creates pending agent)
    2. Approval/rejection via HEL policy
    3. Runtime validation for X-ODIN-Agent headers
    """
    
    def __init__(self, project_id: Optional[str] = None, collection: str = "vai_agents"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.collection = collection
        self._client: Optional[Any] = None
        self._use_firestore = os.getenv("VAI_BACKEND", "firestore") == "firestore"
        self._memory_store: Dict[str, AgentInfo] = {}  # Fallback for testing
    
    @property
    def client(self) -> Any:
        """Lazy Firestore client initialization."""
        if not self._use_firestore:
            return None
        if self._client is None:
            if firestore is None:
                raise RuntimeError("google-cloud-firestore not available")
            self._client = firestore.Client(project=self.project_id)
        return self._client
    
    def register_agent(
        self,
        agent_id: str,
        public_key: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentInfo:
        """
        Register a new agent (status=pending).
        
        Args:
            agent_id: Unique agent identifier
            public_key: Base64-encoded Ed25519 public key
            metadata: Optional agent metadata (name, description, etc.)
        
        Returns:
            AgentInfo with pending status
        """
        if not agent_id or not public_key:
            raise ValueError("agent_id and public_key required")
        
        now_ts = int(time.time())
        agent = AgentInfo(
            agent_id=agent_id,
            public_key=public_key,
            metadata=metadata or {},
            status="pending",
            created_ts=now_ts,
            updated_ts=now_ts,
        )
        
        if self._use_firestore and self.client:
            try:
                doc_ref = self.client.collection(self.collection).document(agent_id)
                doc_ref.set(agent.to_dict())
            except Exception as e:
                raise RuntimeError(f"Failed to register agent in Firestore: {e}")
        else:
            # Memory fallback
            self._memory_store[agent_id] = agent
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID."""
        if not agent_id:
            return None
        
        if self._use_firestore and self.client:
            try:
                doc_ref = self.client.collection(self.collection).document(agent_id)
                doc = doc_ref.get()
                if doc.exists:
                    return AgentInfo.from_dict(doc.to_dict())
            except Exception:
                pass
        else:
            # Memory fallback
            return self._memory_store.get(agent_id)
        
        return None
    
    def update_agent_status(
        self,
        agent_id: str,
        status: str,
        approved_by: Optional[str] = None,
    ) -> bool:
        """
        Update agent status (approve/reject/suspend).
        
        Args:
            agent_id: Agent to update
            status: New status (approved, rejected, suspended)
            approved_by: Who approved/rejected (admin identifier)
        
        Returns:
            True if updated successfully
        """
        if status not in ("approved", "rejected", "suspended", "pending"):
            raise ValueError(f"Invalid status: {status}")
        
        now_ts = int(time.time())
        update_data = {
            "status": status,
            "updated_ts": now_ts,
        }
        
        if status == "approved" and approved_by:
            update_data.update({
                "approved_by": approved_by,
                "approval_ts": now_ts,
            })
        
        if self._use_firestore and self.client:
            try:
                doc_ref = self.client.collection(self.collection).document(agent_id)
                doc_ref.update(update_data)
                return True
            except Exception:
                return False
        else:
            # Memory fallback
            agent = self._memory_store.get(agent_id)
            if agent:
                agent.status = status
                agent.updated_ts = now_ts
                if status == "approved" and approved_by:
                    agent.approved_by = approved_by
                    agent.approval_ts = now_ts
                return True
        
        return False
    
    def list_agents(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentInfo]:
        """
        List agents with optional status filter.
        
        Args:
            status_filter: Filter by status (pending, approved, etc.)
            limit: Maximum number of results
        
        Returns:
            List of AgentInfo objects
        """
        agents = []
        
        if self._use_firestore and self.client:
            try:
                query = self.client.collection(self.collection)
                if status_filter:
                    query = query.where("status", "==", status_filter)
                query = query.limit(limit)
                
                for doc in query.stream():
                    agents.append(AgentInfo.from_dict(doc.to_dict()))
            except Exception:
                pass
        else:
            # Memory fallback
            for agent in self._memory_store.values():
                if status_filter and agent.status != status_filter:
                    continue
                agents.append(agent)
                if len(agents) >= limit:
                    break
        
        return agents
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete agent from registry."""
        if not agent_id:
            return False
        
        if self._use_firestore and self.client:
            try:
                doc_ref = self.client.collection(self.collection).document(agent_id)
                doc_ref.delete()
                return True
            except Exception:
                return False
        else:
            # Memory fallback
            if agent_id in self._memory_store:
                del self._memory_store[agent_id]
                return True
        
        return False
    
    def validate_agent_header(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Validate X-ODIN-Agent header value against registry.
        
        Args:
            agent_id: Agent ID from X-ODIN-Agent header
        
        Returns:
            AgentInfo if valid and approved, None otherwise
        """
        agent = self.get_agent(agent_id)
        if agent and agent.status == "approved":
            return agent
        return None


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get singleton agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def require_approved_agent(agent_id: str) -> AgentInfo:
    """
    Validate agent is approved, raise exception if not.
    
    Args:
        agent_id: Agent ID to validate
    
    Returns:
        AgentInfo for approved agent
    
    Raises:
        ValueError: If agent not found or not approved
    """
    registry = get_agent_registry()
    agent = registry.validate_agent_header(agent_id)
    if not agent:
        raise ValueError(f"Agent '{agent_id}' not found or not approved")
    return agent
