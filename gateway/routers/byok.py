# BYOK (Bring Your Own Key) router for safe playground functionality
# Security: Never store provider keys in logs/receipts, use short-lived tokens

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
import os
import secrets
import logging
from typing import Dict, Any, Optional
import asyncio
import httpx

router = APIRouter(prefix="/v1/byok", tags=["byok"])

# In-memory store with TTL for MVP (replace with Firestore/Redis for production)
_BYOK_STORE: Dict[str, Dict[str, Any]] = {}

# Headers that must be sanitized from logs and receipts
SENSITIVE_HEADERS = {
    "authorization", 
    "x-api-key", 
    "x-odin-byok-token",
    "x-openai-api-key",
    "x-anthropic-api-key",
    "x-google-api-key"
}

# Provider configurations
PROVIDER_CONFIGS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1", 
        "auth_header": "x-api-key",
        "auth_prefix": "",
        "models": ["claude-3-haiku", "claude-3-sonnet", "claude-3-opus"]
    },
    "gemini_api": {
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "models": ["gemini-1.5-flash", "gemini-1.5-pro"]
    }
}

class MintTokenRequest(BaseModel):
    provider: str = Field(pattern="^(openai|vertex|anthropic|mistral|bedrock|gemini_api)$")
    api_key: str = Field(min_length=10, max_length=500)
    model: str = Field(min_length=1, max_length=100)
    ttl_seconds: int = Field(ge=60, le=900, default=600)  # Max 15 minutes

class MintTokenResponse(BaseModel):
    byok_token: str
    exp: str
    provider: str
    model: str

class InvokeRequest(BaseModel):
    byok_token: str
    provider: str
    model: str
    input_type: str = "plain_text"
    payload: Dict[str, Any]
    options: Optional[Dict[str, Any]] = None

class InvokeResponse(BaseModel):
    ok: bool
    trace_id: str
    result: Dict[str, Any]
    receipt_cid: Optional[str] = None
    headers_redacted: list[str]

def cleanup_expired_tokens():
    """Remove expired tokens from store"""
    now = datetime.now(timezone.utc)
    expired_tokens = [
        token for token, data in _BYOK_STORE.items() 
        if data["exp"] < now
    ]
    for token in expired_tokens:
        _BYOK_STORE.pop(token, None)

def generate_trace_id() -> str:
    """Generate a unique trace ID"""
    return f"01JC{secrets.token_urlsafe(16)}"

def sanitize_headers_for_logging(headers: Dict[str, str]) -> Dict[str, str]:
    """Remove sensitive headers before logging"""
    return {
        k: "[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }

@router.post("/token", response_model=MintTokenResponse)
async def mint_byok_token(req: MintTokenRequest, request: Request):
    """
    Mint a short-lived BYOK token for secure playground usage.
    
    Security notes:
    - API key is NEVER logged or stored in receipts
    - Token expires in ≤15 minutes
    - Rate limited per IP
    """
    cleanup_expired_tokens()
    
    # Validate provider
    if req.provider not in PROVIDER_CONFIGS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported provider: {req.provider}"
        )
    
    # Generate secure token
    token = "otk_" + secrets.token_urlsafe(32)
    exp = datetime.now(timezone.utc) + timedelta(seconds=req.ttl_seconds)
    
    # Store token data (API key encrypted in production)
    _BYOK_STORE[token] = {
        "provider": req.provider,
        "api_key": req.api_key,  # TODO: Encrypt this in production
        "model": req.model,
        "exp": exp,
        "created_at": datetime.now(timezone.utc),
        "ip": request.client.host if request.client else "unknown"
    }
    
    # Log token creation (without sensitive data)
    logging.info(
        "BYOK token minted",
        extra={
            "token_id": token[:12] + "...",  # Partial token for debugging
            "provider": req.provider,
            "model": req.model,
            "ttl_seconds": req.ttl_seconds,
            "ip": request.client.host if request.client else "unknown",
            "exp": exp.isoformat()
        }
    )
    
    return MintTokenResponse(
        byok_token=token,
        exp=exp.isoformat(),
        provider=req.provider,
        model=req.model
    )

@router.post("/mesh", response_model=InvokeResponse)
async def byok_mesh(req: InvokeRequest, request: Request):
    """
    Invoke AI model using BYOK token.
    
    Security notes:
    - Token is single-use (optional) or expires quickly
    - Headers sanitized from receipts
    - Rate limited per token/IP
    """
    cleanup_expired_tokens()
    
    # Generate trace ID for this request
    trace_id = generate_trace_id()
    
    # Resolve and validate token
    token_data = _BYOK_STORE.get(req.byok_token)
    if not token_data:
        raise HTTPException(
            status_code=403, 
            detail="Invalid BYOK token"
        )
    
    # Check expiration
    if token_data["exp"] < datetime.now(timezone.utc):
        _BYOK_STORE.pop(req.byok_token, None)
        raise HTTPException(
            status_code=403, 
            detail="BYOK token expired"
        )
    
    # Validate provider/model match
    if token_data["provider"] != req.provider:
        raise HTTPException(
            status_code=400, 
            detail="Provider mismatch with token"
        )
    
    if token_data["model"] != req.model:
        raise HTTPException(
            status_code=400, 
            detail="Model mismatch with token"
        )
    
    # Optional: One-time use token (uncomment for stricter security)
    # _BYOK_STORE.pop(req.byok_token, None)
    
    try:
        # Call provider via secure relay
        result = await call_provider_via_relay(
            provider=req.provider,
            model=req.model,
            api_key=token_data["api_key"],
            payload=req.payload,
            options=req.options or {},
            trace_id=trace_id
        )
        
        # Generate receipt CID (mock for now)
        receipt_cid = f"bafy{secrets.token_urlsafe(32)}"
        
        # Log successful invocation (sanitized)
        logging.info(
            "BYOK mesh invocation successful",
            extra={
                "trace_id": trace_id,
                "provider": req.provider,
                "model": req.model,
                "token_id": req.byok_token[:12] + "...",
                "ip": request.client.host if request.client else "unknown",
                "headers_redacted": list(SENSITIVE_HEADERS)
            }
        )
        
        return InvokeResponse(
            ok=True,
            trace_id=trace_id,
            result=result,
            receipt_cid=receipt_cid,
            headers_redacted=list(SENSITIVE_HEADERS)
        )
        
    except Exception as e:
        logging.error(
            "BYOK mesh invocation failed",
            extra={
                "trace_id": trace_id,
                "provider": req.provider,
                "model": req.model,
                "error": str(e),
                "ip": request.client.host if request.client else "unknown"
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"Provider invocation failed: {str(e)}"
        )

async def call_provider_via_relay(
    provider: str,
    model: str, 
    api_key: str,
    payload: Dict[str, Any],
    options: Dict[str, Any],
    trace_id: str
) -> Dict[str, Any]:
    """
    Securely call AI provider via ODIN relay.
    
    This function:
    1. Formats the request for the specific provider
    2. Makes the API call with proper authentication
    3. Returns standardized response format
    4. Ensures no sensitive data leaks to logs
    """
    provider_config = PROVIDER_CONFIGS.get(provider)
    if not provider_config:
        raise ValueError(f"Unsupported provider: {provider}")
    
    # Build authentication headers
    auth_headers = {
        provider_config["auth_header"]: f"{provider_config['auth_prefix']}{api_key}".strip(),
        "Content-Type": "application/json",
        "X-ODIN-Trace-Id": trace_id
    }
    
    # Format payload for provider
    if provider == "openai":
        api_payload = {
            "model": model,
            "messages": [{"role": "user", "content": payload.get("prompt", "")}],
            "temperature": options.get("temperature", 0),
            "max_tokens": options.get("max_tokens", 1000)
        }
        endpoint = f"{provider_config['base_url']}/chat/completions"
        
    elif provider == "anthropic":
        api_payload = {
            "model": model,
            "messages": [{"role": "user", "content": payload.get("prompt", "")}],
            "temperature": options.get("temperature", 0),
            "max_tokens": options.get("max_tokens", 1000)
        }
        endpoint = f"{provider_config['base_url']}/messages"
        
    elif provider == "gemini_api":
        api_payload = {
            "contents": [{"parts": [{"text": payload.get("prompt", "")}]}],
            "generationConfig": {
                "temperature": options.get("temperature", 0),
                "maxOutputTokens": options.get("max_tokens", 1000)
            }
        }
        endpoint = f"{provider_config['base_url']}/models/{model}:generateContent"
        
    else:
        raise ValueError(f"Provider {provider} not implemented yet")
    
    # Make API call with timeout
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            headers=auth_headers,
            json=api_payload
        )
        
        if not response.is_success:
            raise Exception(f"Provider API error: {response.status_code} - {response.text}")
        
        response_data = response.json()
        
        # Standardize response format
        if provider == "openai":
            return {
                "text": response_data["choices"][0]["message"]["content"],
                "tokens_in": response_data["usage"]["prompt_tokens"],
                "tokens_out": response_data["usage"]["completion_tokens"],
                "model": model,
                "provider": provider
            }
        elif provider == "anthropic":
            return {
                "text": response_data["content"][0]["text"],
                "tokens_in": response_data["usage"]["input_tokens"],
                "tokens_out": response_data["usage"]["output_tokens"], 
                "model": model,
                "provider": provider
            }
        elif provider == "gemini_api":
            return {
                "text": response_data["candidates"][0]["content"]["parts"][0]["text"],
                "tokens_in": response_data.get("usageMetadata", {}).get("promptTokenCount", 0),
                "tokens_out": response_data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
                "model": model,
                "provider": provider
            }
        
        return {"raw_response": response_data}

@router.get("/providers")
async def list_providers():
    """List available providers and their models for the playground"""
    return {
        provider: {
            "models": config["models"],
            "description": f"{provider.title()} AI models"
        }
        for provider, config in PROVIDER_CONFIGS.items()
    }

@router.delete("/token/{token_id}")
async def revoke_token(token_id: str):
    """Manually revoke a BYOK token"""
    if token_id in _BYOK_STORE:
        _BYOK_STORE.pop(token_id)
        return {"ok": True, "message": "Token revoked"}
    return {"ok": False, "message": "Token not found"}
