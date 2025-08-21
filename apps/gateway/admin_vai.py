"""
VAI Admin Router - Agent management endpoints for 0.9.0-beta

Provides admin endpoints for managing the VAI (Verifiable Agent Identity) system:
- POST /v1/admin/agents - Register new agent
- GET /v1/admin/agents - List agents (with optional status filter)
- GET /v1/admin/agents/{agent_id} - Get specific agent
- PUT /v1/admin/agents/{agent_id}/status - Update agent status
- DELETE /v1/admin/agents/{agent_id} - Delete agent
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel, Field

from libs.odin_core.odin.agent_registry import get_agent_registry, AgentInfo
from libs.odin_core.odin.dynamic_reload import require_admin


vai_admin_router = APIRouter()


# Pydantic models for API
class AgentRegistrationRequest(BaseModel):
    """Request to register a new agent."""
    agent_id: str = Field(..., description="Unique agent identifier")
    public_key: str = Field(..., description="Base64-encoded Ed25519 public key")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional agent metadata")


class AgentStatusUpdateRequest(BaseModel):
    """Request to update agent status."""
    status: str = Field(..., description="New status: approved, rejected, suspended")
    approved_by: Optional[str] = Field(None, description="Admin identifier who approved/rejected")


class AgentResponse(BaseModel):
    """Agent information response."""
    agent_id: str
    public_key: str
    metadata: Dict[str, Any]
    status: str
    created_ts: Optional[int]
    updated_ts: Optional[int]
    approved_by: Optional[str]
    approval_ts: Optional[int]
    
    @classmethod
    def from_agent_info(cls, agent: AgentInfo) -> "AgentResponse":
        """Convert AgentInfo to response model."""
        return cls(
            agent_id=agent.agent_id,
            public_key=agent.public_key,
            metadata=agent.metadata,
            status=agent.status,
            created_ts=agent.created_ts,
            updated_ts=agent.updated_ts,
            approved_by=agent.approved_by,
            approval_ts=agent.approval_ts,
        )


class AgentListResponse(BaseModel):
    """List of agents response."""
    agents: List[AgentResponse]
    total: int
    status_filter: Optional[str] = None


def check_admin_auth(request: Request) -> None:
    """Verify admin authentication using existing ODIN admin system."""
    try:
        headers = dict(request.headers)
        require_admin(headers)
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Admin access required: {e}")


@vai_admin_router.post("/v1/admin/agents", response_model=AgentResponse)
async def register_agent(
    req: AgentRegistrationRequest,
    request: Request,
    _: None = Depends(check_admin_auth),
) -> AgentResponse:
    """
    Register a new agent in the VAI system.
    
    Creates agent with status='pending' - requires separate approval via status update.
    """
    try:
        registry = get_agent_registry()
        
        # Check if agent already exists
        existing = registry.get_agent(req.agent_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Agent '{req.agent_id}' already exists with status '{existing.status}'"
            )
        
        # Register new agent
        agent = registry.register_agent(
            agent_id=req.agent_id,
            public_key=req.public_key,
            metadata=req.metadata,
        )
        
        return AgentResponse.from_agent_info(agent)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")


@vai_admin_router.get("/v1/admin/agents", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, suspended)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    _: None = Depends(check_admin_auth),
) -> AgentListResponse:
    """
    List agents with optional status filtering.
    
    Query parameters:
    - status: Filter by agent status (optional)
    - limit: Maximum results (1-1000, default 100)
    """
    try:
        registry = get_agent_registry()
        agents = registry.list_agents(status_filter=status, limit=limit)
        
        agent_responses = [AgentResponse.from_agent_info(agent) for agent in agents]
        
        return AgentListResponse(
            agents=agent_responses,
            total=len(agent_responses),
            status_filter=status,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {e}")


# Health check for VAI system - must come before {agent_id} route
@vai_admin_router.get("/v1/admin/agents/_health")
async def vai_health_check(
    request: Request,
    _: None = Depends(check_admin_auth),
) -> Dict[str, Any]:
    """Check VAI system health and configuration."""
    try:
        registry = get_agent_registry()
        
        # Test basic operations
        test_success = True
        backend_type = "firestore" if registry._use_firestore else "memory"
        
        # Count agents by status
        status_counts = {}
        try:
            for status in ["pending", "approved", "rejected", "suspended"]:
                agents = registry.list_agents(status_filter=status, limit=1000)
                status_counts[status] = len(agents)
        except Exception:
            test_success = False
        
        return {
            "healthy": test_success,
            "backend": backend_type,
            "project_id": registry.project_id,
            "collection": registry.collection,
            "status_counts": status_counts,
            "timestamp": int(time.time()),
        }
    
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": int(time.time()),
        }


@vai_admin_router.get("/v1/admin/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    request: Request,
    _: None = Depends(check_admin_auth),
) -> AgentResponse:
    """Get specific agent by ID."""
    try:
        registry = get_agent_registry()
        agent = registry.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        return AgentResponse.from_agent_info(agent)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {e}")


@vai_admin_router.put("/v1/admin/agents/{agent_id}/status", response_model=AgentResponse)
async def update_agent_status(
    agent_id: str,
    req: AgentStatusUpdateRequest,
    request: Request,
    _: None = Depends(check_admin_auth),
) -> AgentResponse:
    """
    Update agent status (approve/reject/suspend).
    
    Status values:
    - approved: Agent can be used for authentication
    - rejected: Agent registration denied
    - suspended: Previously approved agent temporarily disabled
    - pending: Reset to pending state
    """
    try:
        registry = get_agent_registry()
        
        # Verify agent exists
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        # Update status
        success = registry.update_agent_status(
            agent_id=agent_id,
            status=req.status,
            approved_by=req.approved_by,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update agent status")
        
        # Return updated agent
        updated_agent = registry.get_agent(agent_id)
        if not updated_agent:
            raise HTTPException(status_code=500, detail="Agent disappeared after update")
        
        return AgentResponse.from_agent_info(updated_agent)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent status: {e}")


@vai_admin_router.delete("/v1/admin/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    request: Request,
    _: None = Depends(check_admin_auth),
) -> Dict[str, Any]:
    """Delete agent from registry."""
    try:
        registry = get_agent_registry()
        
        # Verify agent exists
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        
        # Delete agent
        success = registry.delete_agent(agent_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete agent")
        
        return {
            "success": True,
            "message": f"Agent '{agent_id}' deleted successfully",
            "deleted_agent": AgentResponse.from_agent_info(agent).dict(),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {e}")
