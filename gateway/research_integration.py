"""
ODIN Research Engine FastAPI integration.

Wires the research router into the main Gateway application.
"""

from fastapi import FastAPI
from gateway.routers.research import router as research_router
from gateway.middleware.hel_policy import create_hel_enforcer


def setup_research_engine(app: FastAPI):
    """Set up the Research Engine with the main app."""
    
    # Add research router
    app.include_router(research_router, prefix="/api")
    
    # Add HEL enforcement middleware
    hel_enforcer = create_hel_enforcer()
    
    @app.middleware("http")
    async def hel_middleware(request, call_next):
        """Enforce HEL policies on research endpoints."""
        
        if request.url.path.startswith("/api/v1/"):
            # Extract request info
            headers = dict(request.headers)
            body_size = int(headers.get("content-length", 0))
            realm = headers.get("x-odin-target-realm", "business")
            
            # Validate against HEL policy
            error = hel_enforcer.validate_request(headers, body_size, realm)
            if error:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=f"HEL Policy Violation: {error}")
        
        response = await call_next(request)
        return response
    
    return app
