"""
ODIN Gateway Roaming Routes

Implements AI-to-AI roaming pass generation and validation.
"""
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from typing import Dict, Any, List, Optional
import time
import os
from pydantic import BaseModel, Field

from ..constants import GATEWAY_VERSION
from odin.roaming import (
    RoamingPassGenerator, RoamingPassVerifier, load_roaming_config,
    generate_ed25519_keypair, create_roaming_receipt_block,
    roaming_valid, roaming_scope_contains
)


router = APIRouter(prefix="/v1/roaming", tags=["roaming"])


class RoamingPassRequest(BaseModel):
    """Request to mint a roaming pass."""
    did: str = Field(..., description="Agent DID")
    aud: str = Field(..., description="Visited Gateway URL")
    realm_dst: str = Field(..., description="Destination realm")
    scope: List[str] = Field(..., description="Allowed operations", example=["mesh:post", "translate:read"])
    ttl_seconds: int = Field(..., description="Time to live in seconds", ge=1, le=3600)
    realm_src: Optional[str] = Field("default", description="Source realm")
    bind: Optional[Dict[str, str]] = Field(None, description="Optional PoP binding")


class RoamingPassResponse(BaseModel):
    """Response from minting a roaming pass."""
    pass_token: str = Field(..., alias="pass", description="X-ODIN-Roaming-Pass header value")
    exp: str = Field(..., description="Expiration time (ISO 8601)")
    jti: str = Field(..., description="JWT ID (ULID)")
    scope: List[str] = Field(..., description="Granted scope")
    realm_src: str = Field(..., description="Source realm")
    realm_dst: str = Field(..., description="Destination realm")


# Global state (would be dependency injected in real implementation)
_roaming_generator: Optional[RoamingPassGenerator] = None
_roaming_verifier: Optional[RoamingPassVerifier] = None
_roaming_config = None


def get_roaming_generator() -> RoamingPassGenerator:
    """Get roaming pass generator (dependency)."""
    global _roaming_generator
    if not _roaming_generator:
        # Initialize with generated keypair (in production, load from secure storage)
        private_key, _ = generate_ed25519_keypair()
        gateway_url = os.getenv("ODIN_GATEWAY_BASE_URL", "https://localhost:8080")
        _roaming_generator = RoamingPassGenerator(
            gateway_base_url=gateway_url,
            private_key=private_key,
            kid=f"home-gw-{time.strftime('%Y-%m')}"
        )
    return _roaming_generator


def get_roaming_verifier() -> RoamingPassVerifier:
    """Get roaming pass verifier (dependency)."""
    global _roaming_verifier, _roaming_config
    if not _roaming_verifier:
        # Load configuration
        config_path = "configs/roaming/trust_anchors.yaml"
        if os.path.exists(config_path):
            _roaming_config = load_roaming_config(config_path)
        else:
            # Empty config for testing
            from odin.roaming import RoamingConfig
            _roaming_config = RoamingConfig(version=1, issuers=[])
        
        gateway_url = os.getenv("ODIN_GATEWAY_BASE_URL", "https://localhost:8080")
        _roaming_verifier = RoamingPassVerifier(_roaming_config, gateway_url)
    
    return _roaming_verifier


def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> bool:
    """Verify admin key for roaming pass generation."""
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key header")
    
    expected_key = os.getenv("ODIN_ADMIN_KEY", "test-admin-key")
    if x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    return True


@router.post("/pass", response_model=RoamingPassResponse)
async def mint_roaming_pass(
    request: RoamingPassRequest,
    generator: RoamingPassGenerator = Depends(get_roaming_generator),
    _: bool = Depends(verify_admin_key)
) -> RoamingPassResponse:
    """
    Mint a roaming pass for an agent to visit another realm.
    
    Admin-gated endpoint that creates short-lived, cryptographically
    verifiable passes for AI-to-AI roaming between ODIN realms.
    """
    try:
        # Validate DID format (basic check)
        if not request.did.startswith("did:odin:"):
            raise HTTPException(status_code=400, detail="Invalid DID format")
        
        # Validate scope format
        valid_scope_prefixes = ["mesh:", "translate:", "bridge:", "admin:"]
        for scope in request.scope:
            if not any(scope.startswith(prefix) for prefix in valid_scope_prefixes):
                raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")
        
        # Clamp TTL based on configuration (for now, max 10 minutes)
        max_ttl = 600  # 10 minutes
        clamped_ttl = min(request.ttl_seconds, max_ttl)
        
        # Generate pass
        pass_token, metadata = generator.mint_pass(
            agent_did=request.did,
            audience=request.aud,
            realm_dst=request.realm_dst,
            scope=request.scope,
            ttl_seconds=clamped_ttl,
            realm_src=request.realm_src or "default",
            bind=request.bind
        )
        
        return RoamingPassResponse(
            pass_token=pass_token,
            exp=metadata["exp"],
            jti=metadata["jti"],
            scope=metadata["scope"],
            realm_src=metadata["realm_src"],
            realm_dst=metadata["realm_dst"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mint roaming pass: {str(e)}")


@router.get("/config")
async def get_roaming_config(
    _: bool = Depends(verify_admin_key)
) -> Dict[str, Any]:
    """Get current roaming configuration (admin only)."""
    global _roaming_config
    if not _roaming_config:
        get_roaming_verifier()  # Initialize config
    
    return {
        "version": _roaming_config.version,
        "issuers_count": len(_roaming_config.issuers),
        "issuers": [
            {
                "name": issuer.name,
                "iss": issuer.iss,
                "realms_allowed": issuer.realms_allowed,
                "max_ttl_seconds": issuer.max_ttl_seconds
            }
            for issuer in _roaming_config.issuers
        ]
    }


def validate_roaming_headers(
    request: Request,
    x_odin_agent: Optional[str] = Header(None),
    x_odin_target_realm: Optional[str] = Header(None),
    x_odin_roaming_pass: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Middleware-style function to validate roaming headers.
    
    Returns roaming claims if valid, None if no roaming pass, 
    raises HTTPException if invalid.
    """
    if not x_odin_roaming_pass:
        return None  # No roaming pass provided
    
    if not x_odin_agent:
        raise HTTPException(status_code=400, detail="Missing X-ODIN-Agent header for roaming")
    
    if not x_odin_target_realm:
        raise HTTPException(status_code=400, detail="Missing X-ODIN-Target-Realm header for roaming")
    
    # Determine operation from request path
    path = request.url.path
    if "/mesh" in path:
        operation = "mesh:post"
    elif "/translate" in path:
        operation = "translate:read"
    elif "/bridge" in path:
        operation = "bridge:post"
    else:
        operation = "unknown"
    
    # Verify pass
    verifier = get_roaming_verifier()
    valid, claims, error = verifier.verify_pass(
        roaming_pass=x_odin_roaming_pass,
        agent_did=x_odin_agent,
        target_realm=x_odin_target_realm,
        requested_operation=operation
    )
    
    if not valid:
        status_code = 403
        error_messages = {
            "expired": "Roaming pass has expired",
            "issuer_not_trusted": "Roaming pass issuer not trusted",
            "sig_invalid": "Invalid roaming pass signature",
            "agent_mismatch": "Agent DID mismatch in roaming pass",
            "realm_mismatch": "Target realm mismatch in roaming pass",
            "scope_mismatch": "Insufficient scope in roaming pass",
            "invalid_audience": "Invalid audience in roaming pass"
        }
        
        detail = error_messages.get(error, f"Invalid roaming pass: {error}")
        raise HTTPException(status_code=status_code, detail=detail)
    
    # Add verification flag
    claims["verified"] = True
    return claims


# Helper function to add roaming block to receipts
def add_roaming_to_receipt(receipt: Dict[str, Any], roaming_claims: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Add roaming block to receipt if roaming was used."""
    if roaming_claims:
        receipt["roaming"] = create_roaming_receipt_block(roaming_claims, roaming_claims.get("verified", False))
    return receipt
