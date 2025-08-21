"""
Enhanced HEL Middleware with Federation Integration

Integrates RTN transparency logging and Federation metering.
"""

import asyncio
import time
import hashlib
import json
from typing import Dict, Any, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

from odin.rtn import get_rtn_service
from odin.federation import get_federation_service


class EnhancedHELMiddleware(BaseHTTPMiddleware):
    """Enhanced HEL middleware with RTN and Federation integration."""
    
    def __init__(self, app, hel_config: Optional[Dict[str, Any]] = None):
        super().__init__(app)
        self.hel_config = hel_config or {}
        
        # RTN integration
        self.rtn_enabled = self.hel_config.get("rtn_enabled", True)
        self.rtn_require_inclusion = self.hel_config.get("rtn_require_inclusion", False)
        
        # Federation integration  
        self.federation_enabled = self.hel_config.get("federation_enabled", True)
        self.auto_meter_federation = self.hel_config.get("auto_meter_federation", True)
        
        # Default unit counting
        self.default_unit_type = self.hel_config.get("default_unit_type", "requests")
        
    async def dispatch(self, request: Request, call_next):
        """Process request with enhanced HEL, RTN, and Federation."""
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        # Extract headers
        roaming_pass_id = request.headers.get("X-Roaming-Pass-ID")
        client_realm = request.headers.get("X-Client-Realm", "unknown")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate metrics
            duration = time.time() - start_time
            status_code = response.status_code
            
            # Create receipt data
            receipt_data = {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "method": request.method,
                "path": str(request.url.path),
                "status_code": status_code,
                "duration_ms": int(duration * 1000),
                "client_realm": client_realm,
                "roaming_pass_id": roaming_pass_id,
                "server_realm": self.hel_config.get("realm", "default")
            }
            
            # RTN Integration - Submit receipt
            if self.rtn_enabled:
                await self._submit_to_rtn(receipt_data)
            
            # Federation Integration - Record usage
            if self.federation_enabled and roaming_pass_id:
                await self._record_federation_usage(
                    roaming_pass_id, receipt_data, request, response
                )
            
            # Add response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Duration-MS"] = str(int(duration * 1000))
            
            if self.rtn_enabled:
                response.headers["X-RTN-Included"] = "true"
            
            return response
            
        except Exception as e:
            # Handle errors
            duration = time.time() - start_time
            
            # Still submit error to RTN for transparency
            if self.rtn_enabled:
                error_receipt = {
                    "trace_id": trace_id,
                    "timestamp": time.time(),
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": 500,
                    "duration_ms": int(duration * 1000),
                    "error": str(e),
                    "client_realm": client_realm,
                    "server_realm": self.hel_config.get("realm", "default")
                }
                await self._submit_to_rtn(error_receipt)
            
            # Re-raise the exception
            raise
    
    async def _submit_to_rtn(self, receipt_data: Dict[str, Any]) -> bool:
        """Submit receipt to RTN transparency log."""
        try:
            # Get RTN service
            rtn = await get_rtn_service()
            
            # Submit receipt
            success = await rtn.submit_receipt(receipt_data)
            
            if success:
                print(f"📋 RTN: Submitted receipt {receipt_data['trace_id']}")
            else:
                print(f"⚠️ RTN: Failed to submit receipt {receipt_data['trace_id']}")
            
            return success
            
        except Exception as e:
            print(f"❌ RTN submission error: {e}")
            return False
    
    async def _record_federation_usage(self, pass_id: str, receipt_data: Dict[str, Any],
                                     request: Request, response: Response) -> bool:
        """Record usage for federation billing."""
        try:
            # Get Federation service
            federation = await get_federation_service()
            
            # Calculate units based on type
            units = self._calculate_units(request, response, receipt_data)
            
            # Record usage
            success = await federation.record_federation_usage(
                pass_id=pass_id,
                units=units,
                service=receipt_data["path"],
                trace_id=receipt_data["trace_id"]
            )
            
            if success:
                print(f"💰 Federation: Recorded {units} units for pass {pass_id}")
            else:
                print(f"⚠️ Federation: Failed to record usage for pass {pass_id}")
            
            return success
            
        except Exception as e:
            print(f"❌ Federation usage recording error: {e}")
            return False
    
    def _calculate_units(self, request: Request, response: Response, 
                        receipt_data: Dict[str, Any]) -> int:
        """Calculate billable units based on unit type."""
        try:
            unit_type = self.default_unit_type
            
            if unit_type == "requests":
                return 1
            
            elif unit_type == "tokens":
                # Try to extract token count from response
                # This would need integration with LLM response parsing
                return self._estimate_tokens(request, response)
            
            elif unit_type == "bytes":
                # Calculate total bytes
                request_size = len(str(request.url)) + sum(len(f"{k}:{v}") for k, v in request.headers.items())
                response_size = len(response.body) if hasattr(response, 'body') else 1024  # Estimate
                return request_size + response_size
            
            elif unit_type == "minutes":
                # Convert duration to minutes (minimum 1)
                duration_minutes = max(1, int(receipt_data["duration_ms"] / 60000))
                return duration_minutes
            
            elif unit_type == "compute_units":
                # Estimate compute units based on duration and complexity
                base_units = max(1, int(receipt_data["duration_ms"] / 100))  # 100ms = 1 unit
                
                # Adjust for path complexity
                if "/chat" in receipt_data["path"] or "/completion" in receipt_data["path"]:
                    base_units *= 3  # LLM calls are more expensive
                elif "/embedding" in receipt_data["path"]:
                    base_units *= 2  # Embedding calls are moderately expensive
                
                return base_units
            
            else:
                return 1  # Default fallback
                
        except Exception as e:
            print(f"Unit calculation error: {e}")
            return 1  # Safe fallback
    
    def _estimate_tokens(self, request: Request, response: Response) -> int:
        """Estimate token count for requests."""
        try:
            # Simple estimation - would need proper tokenizer integration
            request_text = str(request.url) + str(request.headers)
            response_text = str(response.headers)
            
            # Rough estimate: 4 chars per token
            total_chars = len(request_text) + len(response_text)
            estimated_tokens = max(1, total_chars // 4)
            
            return estimated_tokens
            
        except Exception:
            return 1  # Safe fallback


# HEL Configuration Builder
def build_hel_config(
    realm: str = "default",
    rtn_enabled: bool = True,
    rtn_require_inclusion: bool = False,
    federation_enabled: bool = True,
    auto_meter_federation: bool = True,
    default_unit_type: str = "requests"
) -> Dict[str, Any]:
    """Build HEL configuration."""
    return {
        "realm": realm,
        "rtn_enabled": rtn_enabled,
        "rtn_require_inclusion": rtn_require_inclusion,
        "federation_enabled": federation_enabled,
        "auto_meter_federation": auto_meter_federation,
        "default_unit_type": default_unit_type
    }


# Integration Health Check
async def integration_health_check() -> Dict[str, Any]:
    """Check integration health of RTN and Federation."""
    health_status = {
        "status": "healthy",
        "components": {},
        "message": "All integrations operational"
    }
    
    try:
        # Check RTN
        rtn = await get_rtn_service()
        rtn_health = await rtn.health_check()
        health_status["components"]["rtn"] = rtn_health
        
        # Check Federation
        federation = await get_federation_service()
        federation_stats = await federation.get_federation_stats()
        health_status["components"]["federation"] = {
            "status": "healthy" if federation_stats.get("federation_status") == "operational" else "degraded",
            "stats": federation_stats
        }
        
        # Overall status
        component_statuses = [comp.get("status", "unknown") for comp in health_status["components"].values()]
        
        if any(status == "error" for status in component_statuses):
            health_status["status"] = "error"
            health_status["message"] = "Some integrations have errors"
        elif any(status == "degraded" for status in component_statuses):
            health_status["status"] = "degraded"
            health_status["message"] = "Some integrations are degraded"
        
    except Exception as e:
        health_status = {
            "status": "error",
            "message": f"Integration health check failed: {e}",
            "components": {}
        }
    
    return health_status


# Example usage and configuration
EXAMPLE_HEL_CONFIG = {
    "realm": "odin-prod",
    "rtn_enabled": True,
    "rtn_require_inclusion": True,  # Require RTN inclusion for compliance
    "federation_enabled": True,
    "auto_meter_federation": True,
    "default_unit_type": "compute_units"  # Most fair for AI workloads
}
