"""
VAI (Verifiable Agent Identity) Middleware

Processes X-ODIN-Agent headers and validates agent identity for 0.9.0-beta.
Integrates with existing middleware stack for seamless operation.
"""
from __future__ import annotations

import os
import time
from typing import Optional, Any

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from libs.odin_core.odin.agent_registry import get_agent_registry, AgentInfo


class VAIMiddleware(BaseHTTPMiddleware):
    """
    VAI (Verifiable Agent Identity) middleware for processing X-ODIN-Agent headers.
    
    Features:
    - Validates X-ODIN-Agent header against agent registry
    - Ensures agent is approved before allowing request
    - Adds agent info to request.state for downstream use
    - Optionally enforces VAI on specific routes
    - Integrates with existing ODIN metrics
    """
    
    def __init__(self, app, enforce_routes: Optional[list] = None):
        super().__init__(app)
        self.enforce_routes = enforce_routes or self._parse_enforce_routes()
        self.header_name = os.getenv("VAI_HEADER_NAME", "X-ODIN-Agent")
        self.require_vai = os.getenv("VAI_REQUIRE", "0") != "0"
        
        # For testing: if enforce_routes is explicitly passed, use it
        if enforce_routes is not None:
            self.enforce_routes = enforce_routes
    
    def _parse_enforce_routes(self) -> list:
        """Parse VAI enforcement routes from environment."""
        routes_env = os.getenv("VAI_ENFORCE_ROUTES", "")
        if not routes_env:
            return []
        return [route.strip() for route in routes_env.split(",") if route.strip()]
    
    def _should_enforce_vai(self, path: str) -> bool:
        """Check if VAI should be enforced for this path."""
        if self.require_vai:
            return True
        
        for route_prefix in self.enforce_routes:
            if path.startswith(route_prefix):
                return True
        
        return False
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process VAI header and validate agent identity."""
        path = request.url.path
        
        # Skip VAI for admin routes (they use separate ODIN_ADMIN_KEY auth)
        if path.startswith("/v1/admin/"):
            return await call_next(request)
        
        # Skip VAI for health/discovery endpoints
        if path in ["/health", "/ready", "/.well-known/odin/discovery.json"]:
            return await call_next(request)
        
        # Check if VAI enforcement is required for this route
        should_enforce = self._should_enforce_vai(path)
        
        # Extract X-ODIN-Agent header
        agent_id = request.headers.get(self.header_name)
        
        # Initialize request state
        request.state.vai_agent = None
        request.state.vai_validated = False
        
        if agent_id:
            try:
                # Validate agent against registry
                registry = get_agent_registry()
                agent = registry.validate_agent_header(agent_id)
                
                if agent:
                    # Agent is approved - add to request state
                    request.state.vai_agent = agent
                    request.state.vai_validated = True
                    
                    # Increment metrics
                    try:
                        from apps.gateway.metrics import vai_requests_total
                        vai_requests_total.labels(
                            agent_id=agent_id,
                            status="approved",
                            path=path
                        ).inc()
                    except ImportError:
                        pass
                elif should_enforce:
                    # Agent not approved but enforcement required
                    try:
                        from apps.gateway.metrics import vai_requests_total
                        vai_requests_total.labels(
                            agent_id=agent_id,
                            status="rejected",
                            path=path
                        ).inc()
                    except ImportError:
                        pass
                    
                    raise HTTPException(
                        status_code=403,
                        detail=f"Agent '{agent_id}' not found or not approved",
                        headers={"X-ODIN-VAI-Status": "rejected"}
                    )
            except HTTPException:
                raise
            except Exception as e:
                if should_enforce:
                    raise HTTPException(
                        status_code=500,
                        detail=f"VAI validation error: {e}",
                        headers={"X-ODIN-VAI-Status": "error"}
                    )
                # Non-fatal if enforcement not required
        elif should_enforce:
            # No agent header but enforcement required
            try:
                from apps.gateway.metrics import vai_requests_total
                vai_requests_total.labels(
                    agent_id="",
                    status="missing",
                    path=path
                ).inc()
            except ImportError:
                pass
            
            raise HTTPException(
                status_code=400,
                detail=f"X-ODIN-Agent header required for {path}",
                headers={"X-ODIN-VAI-Status": "missing"}
            )
        
        # Continue with request
        response = await call_next(request)
        
        # Add VAI status to response headers
        if hasattr(request.state, 'vai_validated') and request.state.vai_validated:
            response.headers["X-ODIN-VAI-Status"] = "validated"
            if hasattr(request.state, 'vai_agent') and request.state.vai_agent:
                response.headers["X-ODIN-VAI-Agent"] = request.state.vai_agent.agent_id
        
        return response


def get_vai_agent_from_request(request: Request) -> Optional[AgentInfo]:
    """
    Helper function to get validated VAI agent from request state.
    
    Args:
        request: FastAPI request object
    
    Returns:
        AgentInfo if validated, None otherwise
    """
    try:
        if hasattr(request.state, 'vai_validated') and request.state.vai_validated:
            return getattr(request.state, 'vai_agent', None)
    except Exception:
        pass
    return None


def require_vai_agent(request: Request) -> AgentInfo:
    """
    Require validated VAI agent, raise exception if not present.
    
    Args:
        request: FastAPI request object
    
    Returns:
        AgentInfo for validated agent
    
    Raises:
        HTTPException: If no validated agent found
    """
    agent = get_vai_agent_from_request(request)
    if not agent:
        raise HTTPException(
            status_code=403,
            detail="Valid X-ODIN-Agent header required",
            headers={"X-ODIN-VAI-Status": "required"}
        )
    return agent
