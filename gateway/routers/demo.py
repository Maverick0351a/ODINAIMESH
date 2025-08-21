# Demo model router for zero-friction playground trials
# Uses internal demo credentials with tight rate limits

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import asyncio
import secrets
import logging
from datetime import datetime
import os

router = APIRouter(prefix="/v1/demo", tags=["demo"])

# Demo model configurations with tight limits
DEMO_MODELS = {
    "gemini-1.5-flash": {
        "provider": "gemini_api",
        "max_tokens": 500,
        "rate_limit": "10/hour",
        "description": "Fast, efficient model for quick testing"
    },
    "gpt-4o-mini": {
        "provider": "openai", 
        "max_tokens": 500,
        "rate_limit": "5/hour",
        "description": "Compact OpenAI model for demonstrations"
    }
}

# Demo API keys (from environment for security)
DEMO_CREDENTIALS = {
    "openai": os.getenv("DEMO_OPENAI_API_KEY"),
    "gemini_api": os.getenv("DEMO_GEMINI_API_KEY")
}

class DemoMeshRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    model: str = Field(default="gemini-1.5-flash")
    temperature: float = Field(ge=0, le=1, default=0)
    max_tokens: int = Field(ge=1, le=500, default=200)

class DemoMeshResponse(BaseModel):
    ok: bool
    trace_id: str
    result: Dict[str, Any]
    model_info: Dict[str, Any]
    usage_limits: Dict[str, Any]

def generate_trace_id() -> str:
    """Generate a unique trace ID for demo requests"""
    return f"demo_{secrets.token_urlsafe(12)}"

@router.post("/mesh", response_model=DemoMeshResponse)
async def demo_mesh(req: DemoMeshRequest, request: Request):
    """
    Invoke demo models with zero friction and tight limits.
    
    Features:
    - No API key required from user
    - Tight rate limits to prevent abuse
    - Safe for public demo usage
    - Quick response for immediate gratification
    """
    trace_id = generate_trace_id()
    
    # Validate model
    if req.model not in DEMO_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Demo model '{req.model}' not available. Choose from: {list(DEMO_MODELS.keys())}"
        )
    
    model_config = DEMO_MODELS[req.model]
    provider = model_config["provider"]
    
    # Check if we have demo credentials for this provider
    if not DEMO_CREDENTIALS.get(provider):
        raise HTTPException(
            status_code=503,
            detail=f"Demo credentials not configured for {provider}"
        )
    
    # Enforce demo limits
    max_tokens = min(req.max_tokens, model_config["max_tokens"])
    
    try:
        # Import the BYOK function to reuse provider calling logic
        from .byok import call_provider_via_relay
        
        # Call provider using demo credentials
        result = await call_provider_via_relay(
            provider=provider,
            model=req.model,
            api_key=DEMO_CREDENTIALS[provider],
            payload={"prompt": req.prompt},
            options={
                "temperature": req.temperature,
                "max_tokens": max_tokens
            },
            trace_id=trace_id
        )
        
        # Add demo-specific metadata
        result["demo_mode"] = True
        result["rate_limit_info"] = model_config["rate_limit"]
        
        # Log demo usage (safe to log - no user credentials)
        logging.info(
            "Demo mesh invocation",
            extra={
                "trace_id": trace_id,
                "model": req.model,
                "provider": provider,
                "prompt_length": len(req.prompt),
                "tokens_out": result.get("tokens_out", 0),
                "ip": request.client.host if request.client else "unknown"
            }
        )
        
        return DemoMeshResponse(
            ok=True,
            trace_id=trace_id,
            result=result,
            model_info={
                "name": req.model,
                "provider": provider,
                "description": model_config["description"],
                "max_tokens": model_config["max_tokens"]
            },
            usage_limits={
                "rate_limit": model_config["rate_limit"],
                "max_prompt_length": 2000,
                "max_response_tokens": model_config["max_tokens"],
                "demo_mode": True
            }
        )
        
    except Exception as e:
        logging.error(
            "Demo mesh invocation failed",
            extra={
                "trace_id": trace_id,
                "model": req.model,
                "error": str(e),
                "ip": request.client.host if request.client else "unknown"
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"Demo model invocation failed: {str(e)}"
        )

@router.get("/models")
async def list_demo_models():
    """List available demo models with their limits and descriptions"""
    return {
        "models": {
            model: {
                "description": config["description"],
                "provider": config["provider"],
                "max_tokens": config["max_tokens"],
                "rate_limit": config["rate_limit"]
            }
            for model, config in DEMO_MODELS.items()
        },
        "usage_info": {
            "no_api_key_required": True,
            "rate_limited": True,
            "max_prompt_length": 2000,
            "demo_purpose_only": True
        }
    }

@router.get("/health")
async def demo_health():
    """Health check for demo endpoints"""
    available_models = []
    unavailable_models = []
    
    for model, config in DEMO_MODELS.items():
        provider = config["provider"]
        if DEMO_CREDENTIALS.get(provider):
            available_models.append(model)
        else:
            unavailable_models.append(model)
    
    return {
        "status": "healthy" if available_models else "degraded",
        "available_models": available_models,
        "unavailable_models": unavailable_models,
        "demo_credentials_configured": len(available_models) > 0
    }
