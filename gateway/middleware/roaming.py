"""
ODIN Gateway Roaming Middleware

Handles X-ODIN-Roaming-Pass header validation and HEL integration.
"""
from fastapi import Request, HTTPException
from typing import Optional, Dict, Any
import time

from gateway.routers.roaming import validate_roaming_headers, add_roaming_to_receipt


class RoamingMiddleware:
    """Middleware to handle roaming pass validation."""
    
    def __init__(self):
        self.metrics = {
            "accept_total": 0,
            "reject_total": 0,
            "reject_reasons": {}
        }
    
    async def __call__(self, request: Request, call_next):
        """Process request with roaming validation."""
        # Check if this is a roaming request
        roaming_pass = request.headers.get("x-odin-roaming-pass")
        
        if roaming_pass:
            try:
                # Validate roaming headers
                roaming_claims = validate_roaming_headers(request)
                
                # Store roaming claims in request state for later use
                if not hasattr(request.state, "roaming"):
                    request.state.roaming = roaming_claims
                
                self.metrics["accept_total"] += 1
                
            except HTTPException as e:
                # Log rejection reason
                reason = self._extract_reason_from_detail(e.detail)
                self.metrics["reject_total"] += 1
                self.metrics["reject_reasons"][reason] = self.metrics["reject_reasons"].get(reason, 0) + 1
                
                # Re-raise the exception
                raise e
        
        # Process request
        response = await call_next(request)
        
        # Add roaming info to receipts if needed
        if hasattr(request.state, "roaming") and hasattr(response, "receipt"):
            response.receipt = add_roaming_to_receipt(response.receipt, request.state.roaming)
        
        return response
    
    def _extract_reason_from_detail(self, detail: str) -> str:
        """Extract rejection reason from error detail."""
        if "expired" in detail.lower():
            return "expired"
        elif "issuer" in detail.lower():
            return "issuer_not_trusted"
        elif "signature" in detail.lower():
            return "sig_invalid"
        elif "agent" in detail.lower():
            return "agent_mismatch"
        elif "realm" in detail.lower():
            return "realm_mismatch"
        elif "scope" in detail.lower():
            return "scope_mismatch"
        elif "audience" in detail.lower():
            return "invalid_audience"
        else:
            return "unknown"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get roaming metrics for monitoring."""
        return {
            "odin_roaming_accept_total": self.metrics["accept_total"],
            "odin_roaming_reject_total": self.metrics["reject_total"],
            "odin_roaming_reject_by_reason": self.metrics["reject_reasons"]
        }


# Global middleware instance
roaming_middleware = RoamingMiddleware()


def get_roaming_claims(request: Request) -> Optional[Dict[str, Any]]:
    """Get roaming claims from request state."""
    return getattr(request.state, "roaming", None)


def require_roaming_scope(request: Request, required_scope: str) -> bool:
    """Check if roaming claims include required scope."""
    roaming = get_roaming_claims(request)
    if not roaming:
        return False
    
    scope = roaming.get("scope", [])
    return required_scope in scope


# HEL Integration Functions for middleware
def hel_roaming_valid(request: Request) -> bool:
    """HEL predicate: roaming.valid"""
    roaming = get_roaming_claims(request)
    return roaming is not None and roaming.get("verified", False)


def hel_roaming_scope_contains(request: Request, operation: str) -> bool:
    """HEL predicate: roaming.scope CONTAINS operation"""
    roaming = get_roaming_claims(request)
    if not roaming:
        return False
    return operation in roaming.get("scope", [])


def hel_roaming_realm_dst_matches(request: Request, expected_realm: str) -> bool:
    """HEL predicate: roaming.realm_dst == expected_realm"""
    roaming = get_roaming_claims(request)
    if not roaming:
        return False
    return roaming.get("realm_dst") == expected_realm
